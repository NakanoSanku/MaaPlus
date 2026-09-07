"""Tk desktop authoring UI. Native work happens off the Tk thread and outside this process."""
from __future__ import annotations

import io
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from .engine import WorkerClient
from .project import KINDS, Project
from .testing import overlay, run_suite


class Fields(simpledialog.Dialog):
    def __init__(self, parent, title, values):
        self.values = values
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        self.entries = {}
        for row, (key, (label, value)) in enumerate(self.values.items()):
            ttk.Label(master, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=6)
            entry = ttk.Entry(master, width=56)
            entry.insert(0, str(value))
            entry.grid(row=row, column=1, padx=5, pady=6)
            self.entries[key] = entry
        return next(iter(self.entries.values()))

    def apply(self):
        self.result = {key: entry.get().strip() for key, entry in self.entries.items()}


class Studio:
    def __init__(self, root: tk.Tk, project: Project | None = None, worker=None):
        self.root = root
        self.project = project
        self.worker = worker or WorkerClient()
        self.results_queue = queue.Queue()
        self.cancelled = threading.Event()
        self.busy = self.closed = False
        self.page_id = self.element_id = self.shot_id = None
        self.frame = self.photo = None
        self.source = {"kind": "import"}
        self.matches = []
        self.scale = 1.0
        self.drag_start = self.selection = None
        self.form_dirty = self.filling = False
        self.resample = False
        self.vars = {}
        self.live = tk.BooleanVar(value=False)
        self.mode = tk.StringVar(value="crop")
        self.status = tk.StringVar(value="打开项目，或新建一个 UI 开发项目。")
        self.project_title = tk.StringVar()
        self.root.title("MaaPlus UI Studio")
        self.root.geometry("1480x920")
        self.root.minsize(1120, 720)
        style = ttk.Style(self.root)
        if "clam" in style.theme_names() and self.root.tk.call("tk", "windowingsystem") == "x11":
            style.theme_use("clam")
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-s>", lambda _: self.safe(self.save_element))
        self.root.after(80, self.poll)
        self.root.after(600, self.preview_tick)
        if project:
            self.refresh()

    def button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=lambda: self.safe(command))
        button.pack(side="left", padx=3, pady=3)
        return button

    def _build(self):
        toolbar = ttk.Frame(self.root, padding=6)
        toolbar.pack(fill="x")
        for label, command in (("新建项目", self.new_project), ("打开项目", self.open_project),
                               ("新增页面", self.new_page), ("导入截图", self.import_image),
                               ("保存当前截图", self.save_frame), ("生成 Python", self.generate),
                               ("资源检查", self.audit), ("全部回归", self.suite)):
            self.button(toolbar, label, command)
        ttk.Label(self.root, textvariable=self.project_title, padding=(10, 2)).pack(fill="x")
        devices = ttk.Frame(self.root, padding=(6, 2))
        devices.pack(fill="x")
        ttk.Label(devices, text="ADB 路径（可留空）").pack(side="left")
        self.adb = ttk.Entry(devices, width=26)
        self.adb.pack(side="left", padx=4)
        self.button(devices, "发现设备", self.discover)
        self.device_list = ttk.Combobox(devices, state="readonly", width=33)
        self.device_list.pack(side="left", padx=4)
        self.devices = []
        device_actions = ttk.Frame(self.root, padding=(6, 0))
        device_actions.pack(fill="x")
        self.button(device_actions, "连接", self.connect)
        self.button(device_actions, "手动连接", self.manual_connect)
        ttk.Checkbutton(device_actions, text="实时预览", variable=self.live).pack(side="left", padx=4)
        self.button(device_actions, "抓取一帧", self.capture)
        self.button(device_actions, "实时识别", self.live_test)
        self.button(device_actions, "停止 / 断开", self.disconnect)
        ttk.Label(self.root, textvariable=self.status, relief="sunken", padding=6).pack(side="bottom", fill="x")
        body = ttk.Panedwindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=5)
        left = ttk.Frame(body, width=230)
        body.add(left, weight=1)
        ttk.Button(left, text="打开选中截图", command=lambda: self.safe(self.select_shot)).pack(side="bottom", fill="x", pady=3)
        ttk.Label(left, text="页面 / 元素").pack(anchor="w")
        page_actions = ttk.Frame(left)
        page_actions.pack(fill="x")
        self.button(page_actions, "页面设置", self.edit_page)
        self.button(page_actions, "删除页面", self.delete_page)
        self.tree = ttk.Treeview(left, show="tree", height=15, selectmode="browse")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select_tree)
        ttk.Label(left, text="测试截图（双击回看）").pack(anchor="w", pady=(8, 0))
        self.shots = tk.Listbox(left, height=13, exportselection=False)
        self.shots.pack(fill="both", expand=True)
        self.shots.bind("<Double-Button-1>", lambda _: self.safe(self.select_shot))
        self.shot_ids = []
        center = ttk.Panedwindow(body, orient="vertical")
        body.add(center, weight=5)
        view = ttk.Frame(center)
        center.add(view, weight=4)
        actions = ttk.Frame(view)
        actions.pack(fill="x")
        for label, command in (("适应窗口", self.fit), ("100%", lambda: self.zoom(1.0)),
                               ("放大", lambda: self.zoom(self.scale * 1.25)),
                               ("缩小", lambda: self.zoom(self.scale / 1.25)), ("测试当前截图", self.test_frame)):
            self.button(actions, label, command)
        modes = ttk.Frame(view)
        modes.pack(fill="x")
        ttk.Label(modes, text="拖拽框选：").pack(side="left")
        for label, value in (("模板裁剪", "crop"), ("识别 ROI", "roi"), ("测试预期框", "expect")):
            ttk.Radiobutton(modes, text=label, variable=self.mode, value=value).pack(side="left")
        holder = ttk.Frame(view)
        holder.pack(fill="both", expand=True)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(holder, background="#20252d", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        xs = ttk.Scrollbar(holder, orient="horizontal", command=self.canvas.xview)
        ys = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        xs.grid(row=1, column=0, sticky="ew")
        ys.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=xs.set, yscrollcommand=ys.set)
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.move_drag)
        self.canvas.bind("<ButtonRelease-1>", self.end_drag)
        self.canvas.bind("<ButtonPress-2>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B2-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        notebook = ttk.Notebook(center)
        center.add(notebook, weight=2)
        self.output = tk.Text(notebook, height=12, wrap="word", state="disabled")
        self.code = tk.Text(notebook, height=12, wrap="none", state="disabled")
        notebook.add(self.output, text="识别 / 溯源 / 诊断")
        notebook.add(self.code, text="Python 预览")
        form_container = ttk.Frame(body, width=310)
        body.add(form_container, weight=1)
        form_canvas = tk.Canvas(form_container, width=305, highlightthickness=0)
        form_scroll = ttk.Scrollbar(form_container, orient="vertical", command=form_canvas.yview)
        form_scroll.pack(side="right", fill="y")
        form_canvas.pack(side="left", fill="both", expand=True)
        form_canvas.configure(yscrollcommand=form_scroll.set)
        form = ttk.Frame(form_canvas, padding=8)
        form_window = form_canvas.create_window(0, 0, window=form, anchor="nw")
        form.bind("<Configure>", lambda _: form_canvas.configure(scrollregion=form_canvas.bbox("all")))
        form_canvas.bind("<Configure>", lambda e: form_canvas.itemconfigure(form_window, width=e.width))
        ttk.Label(form, text="元素属性", font=("TkDefaultFont", 12, "bold")).pack(anchor="w", pady=6)
        fields_holder = ttk.Frame(form)
        fields_holder.pack(fill="x")
        self.field_rows = {}
        for key, label, default in (("name", "Python 常量名", "CHALLENGE"), ("kind", "识别方式", "Template"),
                                    ("threshold", "阈值", "0.85"), ("crop", "裁剪 x,y,w,h", ""),
                                    ("roi", "识别 ROI x,y,w,h", ""), ("expected", "OCR expected（JSON 字符串数组）", '["挑战"]'),
                                    ("refs", "组合引用（已有常量名，逗号分隔）", ""), ("box_index", "AllOf box_index", "0"),
                                    ("expect_box", "测试预期框（可空）", "")):
            row = ttk.Frame(fields_holder)
            row.pack(fill="x")
            self.field_rows[key] = row
            ttk.Label(row, text=label).pack(anchor="w", pady=(6, 0))
            var = tk.StringVar(value=default)
            self.vars[key] = var
            var.trace_add("write", self.mark_dirty)
            widget = ttk.Combobox(row, textvariable=var, values=KINDS, state="readonly") if key == "kind" else ttk.Entry(row, textvariable=var)
            widget.pack(fill="x")
        self.vars["kind"].trace_add("write", lambda *_: self.layout_fields())
        self.layout_fields()
        for label, command in (("新元素（清空选择）", self.new_element), ("保存元素  Ctrl+S", self.save_element),
                               ("从当前截图重新取样", self.use_current_source), ("回溯裁剪原图", self.trace),
                               ("删除元素", self.delete_element), ("标记预期：应命中", lambda: self.set_expect(True)),
                               ("标记预期：不应命中", lambda: self.set_expect(False))):
            ttk.Button(form, text=label, command=lambda c=command: self.safe(c)).pack(fill="x", pady=3)
        ttk.Label(form, text="蓝：裁剪；黄：ROI；绿：实际命中。\n缩放仅影响预览，坐标始终是原图像素。\n已有元素默认沿用原图，重取样需显式选择。", wraplength=260).pack(anchor="w", pady=10)

    def layout_fields(self):
        kind = self.vars["kind"].get()
        visible = {"name", "kind", "expect_box"}
        if kind in ("Template", "OCR"):
            visible.update(("crop", "roi", "threshold"))
            if kind == "OCR":
                visible.add("expected")
        else:
            visible.add("refs")
            if kind == "AllOf":
                visible.add("box_index")
        for key, row in self.field_rows.items():
            row.pack_forget()
            if key in visible:
                row.pack(fill="x")

    def mark_dirty(self, *_):
        if not self.filling:
            self.form_dirty = True

    def safe(self, function):
        if self.busy and function != self.disconnect:
            self.status.set("正在执行识别或设备操作；可使用“停止 / 断开”取消。")
            return
        try:
            function()
        except Exception as exc:
            self.status.set(str(exc))
            messagebox.showerror("MaaPlus UI Studio", str(exc), parent=self.root)

    def require_project(self):
        if self.project is None:
            raise ValueError("请先新建或打开项目")
        return self.project

    def require_page(self):
        project = self.require_project()
        if self.page_id is None:
            raise ValueError("请先选择页面")
        return project.page(self.page_id)

    def discard_form(self):
        return not self.form_dirty or messagebox.askyesno("尚未保存", "元素属性尚未保存，丢弃这些修改？", parent=self.root)

    def show_text(self, widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))
        widget.configure(state="disabled")

    def refresh(self):
        project = self.require_project()
        self.project_title.set(f"{project.root}  ·  {project.data['size'][0]}×{project.data['size'][1]}  ·  UI: {project.data['ui_dir']}")
        self.tree.delete(*self.tree.get_children())
        for page in project.data["pages"]:
            self.tree.insert("", "end", iid=page["id"], text=page["name"], open=True)
            for element in page["elements"]:
                self.tree.insert(page["id"], "end", iid=element["id"], text=f"{element['name']}  [{element['kind']}]")
        self.shots.delete(0, "end")
        self.shot_ids = []
        for shot in project.data["screenshots"]:
            self.shot_ids.append(shot["id"])
            self.shots.insert("end", f"{shot['id'][:8]}  {shot['source'].get('name', shot['source'].get('kind', 'image'))}")
        self.show_text(self.code, "\n".join(f"# {name}\n{code}" for name, code in project.render().items()))

    def set_project(self, project):
        self.disconnect()
        self.project = project
        self.page_id = self.element_id = self.shot_id = None
        self.frame = None
        self.matches = []
        self.form_dirty = False
        self.refresh()
        self.draw()
        self.status.set("项目已打开。先创建页面，再导入截图或连接设备。")

    def new_project(self):
        if not self.discard_form():
            return
        root = filedialog.askdirectory(title="选择项目根目录", parent=self.root)
        if not root:
            return
        values = Fields(self.root, "项目路径与识别分辨率", {
            "ui": ("UI Python 目录（相对根目录）", "ui/generated"),
            "resource": ("MaaFramework 资源目录", "resource"),
            "fixtures": ("测试截图目录", "tests/ui"),
            "width": ("运行时截图宽度", "1280"), "height": ("运行时截图高度", "720"),
        }).result
        if values:
            self.set_project(Project.create(root, ui=values["ui"], resource=values["resource"], fixtures=values["fixtures"],
                                            size=(int(values["width"]), int(values["height"]))))

    def open_project(self):
        if not self.discard_form():
            return
        file = filedialog.askopenfilename(title="打开 maaplus-studio.json", filetypes=[("Studio project", "*.json")], parent=self.root)
        if file:
            self.set_project(Project.open(file))

    def new_page(self):
        project = self.require_project()
        if not self.discard_form():
            return
        values = Fields(self.root, "新增页面", {"name": ("Python 页面类名", "ChallengeUI"),
                                              "file": ("Python 文件（项目相对路径）", project.data["ui_dir"] + "/challenge.py")}).result
        if values:
            self.page_id = project.add_page(values["name"], values["file"])
            self.element_id = None
            self.form_dirty = False
            self.refresh()
            self.tree.selection_set(self.page_id)

    def edit_page(self):
        page = self.require_page()
        if not self.discard_form():
            return
        values = Fields(self.root, "页面名称与代码位置", {
            "name": ("Python 页面类名", page["name"]), "file": ("Python 文件相对路径", page["file"]),
        }).result
        if values:
            self.project.update_page(self.page_id, **values)
            self.form_dirty = False
            self.refresh()
            self.status.set("页面已更新。重新生成代码后，资源检查会提示遗留文件；不会自动删除旧文件。")

    def delete_page(self):
        page = self.require_page()
        if messagebox.askyesno("删除页面", f"删除 {page['name']}、元素定义和相关断言？原图、模板和旧代码保留。", parent=self.root):
            self.project.remove_page(self.page_id)
            self.page_id = self.element_id = None
            self.clear_form()
            self.refresh()
            self.draw()

    def select_tree(self, _=None):
        if self.busy or not self.tree.selection():
            return
        selected = self.tree.selection()[0]
        parent = self.tree.parent(selected)
        if selected == self.element_id or (not parent and selected == self.page_id and self.element_id is None):
            return
        if not self.discard_form():
            return
        self.page_id = parent or selected
        self.element_id = selected if parent else None
        if self.element_id:
            element = self.project.element(self.page_id, self.element_id)
            names = {e["id"]: e["name"] for e in self.require_page()["elements"]}
            self.filling = True
            for key in self.vars:
                value = element.get(key, "")
                if key in ("crop", "roi"):
                    value = ",".join(map(str, value))
                elif key == "expected":
                    value = json.dumps(element.get(key, ["挑战"]), ensure_ascii=False)
                elif key == "refs":
                    value = ",".join(names[r] for r in element.get(key, []))
                self.vars[key].set(value)
            self.filling = False
            self.resample = False
            self.form_dirty = False
            self.show_text(self.output, element)
        else:
            self.clear_form()
        self.draw()

    def clear_form(self):
        defaults = dict(name="CHALLENGE", kind="Template", threshold="0.85", crop="", roi="", expected='["挑战"]', refs="", box_index="0", expect_box="")
        self.filling = True
        for key, value in defaults.items():
            self.vars[key].set(value)
        self.filling = False
        self.form_dirty = self.resample = False

    def new_element(self):
        self.require_page()
        if self.discard_form():
            self.element_id = None
            self.clear_form()

    @staticmethod
    def parse_rect(value):
        if not value.strip():
            return None
        values = [int(n.strip()) for n in value.split(",")]
        if len(values) != 4:
            raise ValueError("坐标需要四个整数：x,y,w,h")
        return values

    def save_element(self):
        page = self.require_page()
        kind = self.vars["kind"].get()
        kwargs = dict(name=self.vars["name"].get().strip(), kind=kind, element_id=self.element_id)
        if kind in ("FirstOf", "AllOf"):
            names = {e["name"]: e["id"] for e in page["elements"]}
            refs = [n.strip() for n in self.vars["refs"].get().split(",") if n.strip()]
            if any(n not in names for n in refs):
                raise ValueError("组合引用必须是当前页面已有的常量名")
            kwargs.update(refs=[names[n] for n in refs], box_index=int(self.vars["box_index"].get() or 0))
        else:
            existing = self.project.element(self.page_id, self.element_id) if self.element_id else None
            source = existing.get("source") if existing and not self.resample else None
            if source is None:
                source = self.ensure_saved()
            kwargs.update(shot_id=source, crop=self.parse_rect(self.vars["crop"].get()),
                          roi=self.parse_rect(self.vars["roi"].get()), threshold=float(self.vars["threshold"].get()),
                          expected=json.loads(self.vars["expected"].get()) if kind == "OCR" else None)
        self.element_id = self.project.put_element(self.page_id, **kwargs)
        self.form_dirty = self.resample = False
        self.refresh()
        self.status.set("元素已保存。可继续添加元素；生成 Python 后再执行测试。")
        self.draw()

    def use_current_source(self):
        if self.frame is None:
            raise ValueError("请先打开或抓取一张截图")
        self.resample = True
        self.form_dirty = True
        self.status.set("本次保存将从当前截图重新裁剪；请确认蓝色模板框。")

    def delete_element(self):
        if not self.element_id:
            raise ValueError("请选择元素")
        if messagebox.askyesno("删除元素", "删除元素与相关断言？原始截图和模板文件会保留。", parent=self.root):
            self.project.remove_element(self.page_id, self.element_id)
            self.element_id = None
            self.clear_form()
            self.refresh()
            self.draw()

    def display_frame(self, image, source=None, shot_id=None):
        needs_fit = self.frame is None or self.frame.size != image.size
        self.frame = image.convert("RGB").copy()
        self.source = source or {"kind": "import"}
        self.shot_id = shot_id
        self.matches = []
        self.selection = None
        self.fit() if needs_fit else self.draw()
        self.status.set(f"{image.width}×{image.height} · {'已入库 ' + shot_id[:12] if shot_id else '未保存帧'}")

    def import_image(self):
        self.require_project()
        path = filedialog.askopenfilename(title="导入运行时分辨率截图", filetypes=[("Images", "*.png *.bmp *.jpg *.jpeg")], parent=self.root)
        if path:
            self.live.set(False)
            with Image.open(path) as image:
                shot_id = self.project.add_screenshot(image, {"kind": "import", "name": Path(path).name})
            self.refresh()
            self.display_frame(self.project.image(shot_id), self.project.screenshot(shot_id)["source"], shot_id)

    def ensure_saved(self):
        self.require_project()
        if self.frame is None:
            raise ValueError("请先导入或抓取截图")
        self.live.set(False)
        if self.shot_id is None:
            self.shot_id = self.project.add_screenshot(self.frame, self.source)
            self.refresh()
        return self.shot_id

    def save_frame(self):
        sid = self.ensure_saved()
        self.status.set(f"截图已保存并可溯源：{self.project.screenshot(sid)['path']}")

    def select_shot(self):
        self.require_project()
        selection = self.shots.curselection()
        if selection:
            sid = self.shot_ids[selection[0]]
            self.live.set(False)
            self.display_frame(self.project.image(sid), self.project.screenshot(sid)["source"], sid)
            references = [dict(page=p["name"], file=p["file"], element=e["name"], crop=e["crop"], template=e.get("template"))
                          for p in self.project.data["pages"] for e in p["elements"] if e.get("source") == sid]
            self.show_text(self.output, {"screenshot": self.project.screenshot(sid), "elements": references})

    def trace(self):
        if not self.element_id:
            raise ValueError("请选择元素")
        element = self.project.element(self.page_id, self.element_id)
        if "source" not in element:
            self.show_text(self.output, element)
            return
        sid = element["source"]
        self.live.set(False)
        self.display_frame(self.project.image(sid), self.project.screenshot(sid)["source"], sid)
        self.show_text(self.output, {"page": self.require_page()["name"], "file": self.require_page()["file"],
                                     "element": element, "screenshot": self.project.screenshot(sid),
                                     "cases": [c for c in self.project.data["cases"] if self.element_id in c["expect"]]})

    def fit(self):
        if self.frame:
            self.zoom(min(max(1, self.canvas.winfo_width() - 12) / self.frame.width,
                          max(1, self.canvas.winfo_height() - 12) / self.frame.height, 1.0))

    def zoom(self, value):
        self.scale = max(0.05, min(4.0, value))
        self.draw()

    def draw_box(self, box, color, tag="annotation"):
        x, y, w, h = box
        return self.canvas.create_rectangle(x * self.scale, y * self.scale, (x + w) * self.scale,
                                            (y + h) * self.scale, outline=color, width=2, tags=tag)

    def draw(self):
        self.canvas.delete("all")
        if self.frame is None:
            return
        shown = overlay(self.frame, self.matches) if self.matches else self.frame
        size = (max(1, round(shown.width * self.scale)), max(1, round(shown.height * self.scale)))
        self.photo = ImageTk.PhotoImage(shown.resize(size, Image.Resampling.LANCZOS))
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.configure(scrollregion=(0, 0, *size))
        if self.project and self.shot_id:
            for page in self.project.data["pages"]:
                for element in page["elements"]:
                    if element.get("source") == self.shot_id:
                        self.draw_box(element["crop"], "#57a6ff")
                        x, y, _, _ = element["crop"]
                        self.canvas.create_text(x * self.scale + 3, y * self.scale + 3, anchor="nw", text=element["name"], fill="#57a6ff")
        if self.element_id and self.project:
            element = self.project.element(self.page_id, self.element_id)
            if element.get("source") == self.shot_id:
                self.draw_box(element["crop"], "#57a6ff")
            if "roi" in element:
                self.draw_box(element["roi"], "#ffb340")
        if self.selection:
            self.draw_box(self.selection, "#f6f8fa", "selection")

    def image_point(self, event):
        return (max(0, min(self.frame.width, int(self.canvas.canvasx(event.x) / self.scale))),
                max(0, min(self.frame.height, int(self.canvas.canvasy(event.y) / self.scale))))

    def start_drag(self, event):
        if self.frame is not None and not self.busy:
            self.live.set(False)
            self.drag_start = self.image_point(event)

    def move_drag(self, event):
        if self.drag_start is None:
            return
        x, y = self.image_point(event)
        sx, sy = self.drag_start
        self.selection = [min(sx, x), min(sy, y), abs(x - sx), abs(y - sy)]
        self.canvas.delete("selection")
        self.draw_box(self.selection, "#f6f8fa", "selection")

    def end_drag(self, event):
        if self.drag_start is None:
            return
        self.move_drag(event)
        self.drag_start = None
        if self.selection and min(self.selection[2:]) > 0:
            key = "expect_box" if self.mode.get() == "expect" else self.mode.get()
            self.vars[key].set(",".join(map(str, self.selection)))
            if key == "crop" and not self.vars["roi"].get():
                self.vars["roi"].set(self.vars["crop"].get())
            self.status.set(f"已选 {key}: {self.selection} · 原图像素坐标")

    def generate(self):
        self.require_project()
        if self.form_dirty:
            raise ValueError("请先保存当前元素属性，再生成 Python")
        names = self.project.generate()
        self.refresh()
        self.status.set("已生成：" + ", ".join(names))

    def audit(self):
        self.show_text(self.output, self.require_project().audit())

    def set_expect(self, hit):
        self.require_page()
        if not self.element_id:
            raise ValueError("请先保存或选择要测试的元素")
        sid = self.ensure_saved()
        box = self.parse_rect(self.vars["expect_box"].get()) if hit else None
        self.project.expect(self.page_id, sid, self.element_id, hit, box)
        self.status.set(f"测试断言已保存：{self.project.element(self.page_id, self.element_id)['name']} 应{'命中' if hit else '不命中'}")

    def async_job(self, function, done, message):
        if self.busy:
            return
        self.busy = True
        self.cancelled.clear()
        self.status.set(message)
        def work():
            try:
                self.results_queue.put((done, function(), None))
            except Exception as exc:
                self.results_queue.put((done, None, exc))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            callback, result, error = self.results_queue.get_nowait()
            self.busy = False
            if self.cancelled.is_set():
                self.status.set("操作已取消；再次使用模拟器时请重新连接。")
            elif error:
                self.live.set(False)
                self.status.set(str(error))
                self.show_text(self.output, str(error))
            else:
                try:
                    callback(result)
                except Exception as exc:
                    self.status.set(str(exc))
                    self.show_text(self.output, str(exc))
        except queue.Empty:
            pass
        self.root.after(80, self.poll)

    def discover(self):
        root, adb = str(self.require_project().root), self.adb.get().strip()
        def done(devices):
            self.devices = devices
            self.device_list["values"] = [f"{d['name']} · {d['address']}" for d in devices]
            if devices:
                self.device_list.current(0)
            self.status.set(f"发现 {len(devices)} 个设备。请选择后连接；也可指定模拟器自带的 adb。")
        self.async_job(lambda: self.worker.request("discover", root=root, adb=adb), done, "正在发现设备…")

    def connect(self):
        root = str(self.require_project().root)
        index = self.device_list.current()
        if not 0 <= index < len(self.devices):
            raise ValueError("请先发现并选择设备")
        self.async_job(lambda: self.worker.request("connect", root=root, device=self.devices[index]),
                       lambda _: self.status.set("连接成功。可开启实时预览，或抓取一帧。"), "正在连接模拟器…")

    def manual_connect(self):
        root = str(self.require_project().root)
        values = Fields(self.root, "手动连接 ADB 设备", {
            "adb_path": ("adb 可执行文件完整路径", self.adb.get().strip()),
            "address": ("设备地址或序列号", "127.0.0.1:5555"),
        }).result
        if values:
            if not values["adb_path"] or not values["address"]:
                raise ValueError("手动连接需要 adb 路径与设备地址")
            values["name"] = "manual"
            self.async_job(lambda: self.worker.request("connect", root=root, device=values),
                           lambda _: self.status.set("连接成功。可开启实时预览。"), "正在连接模拟器…")

    def captured(self, result):
        with Image.open(io.BytesIO(result["png"])) as image:
            self.display_frame(image, result["source"])

    def capture(self):
        root = str(self.require_project().root)
        self.live.set(False)
        self.async_job(lambda: self.worker.request("capture", root=root), self.captured, "正在抓取截图…")

    def preview_tick(self):
        if self.closed:
            return
        if self.live.get() and not self.busy and self.project:
            root = str(self.project.root)
            self.async_job(lambda: self.worker.request("capture", root=root),
                           lambda result: self.captured(result) if self.live.get() else None, "实时预览中…")
        self.root.after(600, self.preview_tick)

    def test_frame(self):
        page = self.require_page()
        if self.form_dirty:
            raise ValueError("请先保存元素并生成 Python")
        self.project.check_generated()
        sid = self.ensure_saved()
        page_id, root = page["id"], str(self.project.root)
        def done(results):
            self.show_text(self.output, {"screenshot": sid, "results": results})
            if self.shot_id == sid:
                self.matches = results
                self.draw()
            self.status.set("识别完成。结果仅供观察；回归是否通过由明确的正反样本断言决定。")
        self.async_job(lambda: self.worker.request("recognize", root=root, page_id=page_id, shot_id=sid), done, "正在使用生成的 Python 定义识别…")

    def live_test(self):
        self.require_page()
        self.project.check_generated()
        self.live.set(False)
        root = str(self.project.root)
        def done(result):
            self.captured(result)
            self.test_frame()
        self.async_job(lambda: self.worker.request("capture", root=root), done, "抓取最新帧并识别…")

    def suite(self):
        project = Project.open(self.require_project().root)
        if self.form_dirty:
            raise ValueError("请先保存当前元素")
        self.live.set(False)
        def run():
            def recognize(page_id, shot_id):
                if Project.open(project.root).revision != project.revision:
                    raise RuntimeError("Project changed during the test run; rerun against one revision")
                return self.worker.request("recognize", root=str(project.root), page_id=page_id, shot_id=shot_id)
            return run_suite(project, recognize, cancelled=self.cancelled.is_set)
        def done(report):
            self.show_text(self.output, report)
            self.status.set(f"回归：{report['passed']} 通过 / {report['failed']} 失败 / {report['error']} 异常。报告：.debug/studio-report/index.html")
        self.async_job(run, done, "正在执行截图回归测试…")

    def disconnect(self):
        self.cancelled.set()
        self.live.set(False)
        self.worker.close()
        self.status.set("设备工作进程已停止；再次使用设备时需要重新连接。")

    def close(self):
        if not self.discard_form():
            return
        self.closed = True
        self.cancelled.set()
        self.live.set(False)
        self.worker.close()
        self.root.destroy()


def launch(project=None):
    root = tk.Tk()
    Studio(root, project)
    root.mainloop()
