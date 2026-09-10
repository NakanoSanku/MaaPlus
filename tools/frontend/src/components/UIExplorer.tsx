import * as React from 'react';
import {
  Camera,
  ChevronDown,
  ChevronRight,
  FolderTree,
  Image as ImageIcon,
  Layers,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Type,
  Upload,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog } from './ui/dialog';
import { UIClass, LocatorConfig, BoundScreenshot } from '../types';

interface UIExplorerProps {
  uiClasses: UIClass[];
  selectedClassIndex: number;
  selectedLocatorIndex: number;
  activeScreenshotId: string | null;
  onSelectClass: (index: number) => void;
  onSelectLocator: (classIndex: number, locatorIndex: number) => void;
  onSelectScreenshot: (classIndex: number, screenshot: BoundScreenshot) => void;
  onAddClass: (name: string) => void;
  onDeleteClass: (index: number) => void;
  onAddLocator: (classIndex: number, locator: LocatorConfig) => void;
  onDeleteLocator: (classIndex: number, locatorIndex: number) => void;
  onBindCurrentScreenshot: (classIndex: number) => void;
  onUploadScreenshot: (classIndex: number, file: File) => void;
  onDeleteScreenshot: (classIndex: number, screenshotIndex: number) => void;
  onScanProject: () => void;
  isScanning: boolean;
}

export function UIExplorer({
  uiClasses,
  selectedClassIndex,
  selectedLocatorIndex,
  activeScreenshotId,
  onSelectClass,
  onSelectLocator,
  onSelectScreenshot,
  onAddClass,
  onDeleteClass,
  onAddLocator,
  onDeleteLocator,
  onBindCurrentScreenshot,
  onUploadScreenshot,
  onDeleteScreenshot,
  onScanProject,
  isScanning,
}: UIExplorerProps) {
  const [searchTerm, setSearchTerm] = React.useState('');
  const [expandedClasses, setExpandedClasses] = React.useState<Record<string, boolean>>({ '0': true });
  const [isNewClassDialogOpen, setIsNewClassDialogOpen] = React.useState(false);
  const [newClassName, setNewClassName] = React.useState('');
  const [targetClassForUpload, setTargetClassForUpload] = React.useState(0);
  const uploadInputRef = React.useRef<HTMLInputElement>(null);

  const filteredClasses = uiClasses
    .map((cls, classIndex) => ({
      cls,
      classIndex,
      visible:
        cls.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        cls.locators.some((locator) => locator.name.toLowerCase().includes(searchTerm.toLowerCase())),
    }))
    .filter((item) => item.visible);

  const createClass = () => {
    const raw = newClassName.trim();
    if (!raw) return;
    onAddClass(raw.endsWith('UI') ? raw : `${raw}UI`);
    setNewClassName('');
    setIsNewClassDialogOpen(false);
  };

  const addLocator = (classIndex: number, event: React.MouseEvent) => {
    event.stopPropagation();
    const nextIndex = uiClasses[classIndex].locators.length + 1;
    const name = `target_${nextIndex}`;
    onAddLocator(classIndex, {
      name,
      type: 'Template',
      template: [`assets/image/${name}.png`],
      threshold: 0.85,
      roi: null,
    });
    setExpandedClasses((current) => ({ ...current, [String(classIndex)]: true }));
  };

  const triggerUpload = (classIndex: number, event: React.MouseEvent) => {
    event.stopPropagation();
    setTargetClassForUpload(classIndex);
    uploadInputRef.current?.click();
  };

  return (
    <div className="flex h-full flex-col bg-white text-[#252522] select-none">
      <input
        ref={uploadInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onUploadScreenshot(targetClassForUpload, file);
          event.target.value = '';
        }}
      />

      <div className="shrink-0 border-b border-[#ecece8] p-3">
        <div className="mb-2.5 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2 whitespace-nowrap">
            <FolderTree className="h-4 w-4 shrink-0 text-[#6f6f68]" />
            <span className="text-[12px] font-semibold text-[#2a2a27]">UI 页面</span>
            <span className="rounded-md border border-[#e5e5e1] bg-[#f7f7f5] px-1.5 py-0.5 text-[9px] font-medium text-[#85857d]">
              {uiClasses.length}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              size="icon"
              variant="ghost"
              onClick={onScanProject}
              disabled={isScanning}
              className="h-7 w-7 text-[#77776f]"
              title="扫描项目 UI"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            </Button>
            <Button size="sm" onClick={() => setIsNewClassDialogOpen(true)} className="h-7 px-2.5 text-[10px]">
              <Plus className="h-3.5 w-3.5" />
              新建
            </Button>
          </div>
        </div>

        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#aaa9a2]" />
          <Input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="搜索页面或定位符"
            className="h-8 pl-8 text-[11px]"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {filteredClasses.length === 0 ? (
          <div className="flex h-44 flex-col items-center justify-center px-5 text-center">
            <Layers className="mb-2 h-7 w-7 text-[#c4c4be]" />
            <p className="text-[11px] font-medium text-[#71716a]">没有匹配的页面</p>
            <p className="mt-1 text-[10px] leading-4 text-[#aaa9a2]">新建页面，或扫描项目中的 UI 定义</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredClasses.map(({ cls, classIndex }) => {
              const expanded = expandedClasses[String(classIndex)] ?? true;
              const selected = selectedClassIndex === classIndex;
              const screenshots = cls.screenshots || [];
              return (
                <section
                  key={`${cls.name}-${classIndex}`}
                  className={`overflow-hidden rounded-lg border transition-colors ${
                    selected ? 'border-[#c9c9c3] bg-[#fcfcfa]' : 'border-[#ecece8] bg-white'
                  }`}
                >
                  <div
                    onClick={() => onSelectClass(classIndex)}
                    className={`group flex cursor-pointer items-center gap-2 px-2.5 py-2 ${selected ? 'bg-[#f5f5f2]' : 'hover:bg-[#fafaf8]'}`}
                  >
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        setExpandedClasses((current) => ({ ...current, [String(classIndex)]: !expanded }));
                      }}
                      className="rounded p-0.5 text-[#8b8b84] hover:bg-[#ecece8]"
                    >
                      {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    </button>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline gap-2 whitespace-nowrap">
                        <span className="truncate text-[11px] font-semibold text-[#353532]">{cls.name}</span>
                        <span className="text-[9px] tabular-nums text-[#9a9a93]">
                          {cls.locators.length} 定位符 · {screenshots.length} 样本
                        </span>
                      </div>
                    </div>
                    {uiClasses.length > 1 && (
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteClass(classIndex);
                        }}
                        className="rounded p-1 text-[#b1b1aa] opacity-0 transition-opacity hover:bg-[#fff2f1] hover:text-rose-600 group-hover:opacity-100"
                        title="删除页面"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>

                  {expanded && (
                    <div className="space-y-3 border-t border-[#eeeeea] px-2.5 pb-2.5 pt-2">
                      <div>
                        <div className="mb-1 flex items-center justify-between px-1">
                          <span className="text-[9px] font-semibold tracking-wide text-[#8b8b84]">定位符</span>
                          <button onClick={(event) => addLocator(classIndex, event)} className="flex items-center gap-0.5 text-[9px] font-medium text-[#66665f] hover:text-[#1e1e1c]">
                            <Plus className="h-3 w-3" />添加
                          </button>
                        </div>
                        <div className="space-y-0.5">
                          {cls.locators.length === 0 ? (
                            <div className="rounded-md bg-[#f8f8f6] px-2 py-2 text-[10px] text-[#9a9a93]">暂无定位符</div>
                          ) : (
                            cls.locators.map((locator, locatorIndex) => {
                              const locatorSelected = selected && selectedLocatorIndex === locatorIndex;
                              return (
                                <div
                                  key={`${locator.name}-${locatorIndex}`}
                                  onClick={() => onSelectLocator(classIndex, locatorIndex)}
                                  className={`group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 ${
                                    locatorSelected ? 'bg-[#deded9] text-[#242421]' : 'text-[#66665f] hover:bg-[#f4f4f1]'
                                  }`}
                                >
                                  {locator.type === 'Template' ? (
                                    <ImageIcon className="h-3 w-3 shrink-0 text-[#77776f]" />
                                  ) : (
                                    <Type className="h-3 w-3 shrink-0 text-emerald-600" />
                                  )}
                                  <span className="min-w-0 flex-1 truncate font-mono text-[10px]">{locator.name}</span>
                                  {locator.roi && (
                                    <span className="rounded bg-[#eeeeea] px-1 py-0.5 text-[8px] font-medium text-[#85857d]">ROI</span>
                                  )}
                                  <button
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      onDeleteLocator(classIndex, locatorIndex);
                                    }}
                                    className="rounded p-0.5 text-[#b1b1aa] opacity-0 hover:text-rose-600 group-hover:opacity-100"
                                    title="删除定位符"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </div>
                              );
                            })
                          )}
                        </div>
                      </div>

                      <div className="border-t border-[#eeeeea] pt-2">
                        <div className="mb-1 flex items-center justify-between px-1">
                          <span className="text-[9px] font-semibold tracking-wide text-[#8b8b84]">样本截图</span>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={(event) => {
                                event.stopPropagation();
                                onBindCurrentScreenshot(classIndex);
                              }}
                              className="flex items-center gap-0.5 text-[9px] font-medium text-emerald-700 hover:text-emerald-800"
                            >
                              <Camera className="h-3 w-3" />绑定
                            </button>
                            <button onClick={(event) => triggerUpload(classIndex, event)} className="flex items-center gap-0.5 text-[9px] font-medium text-[#66665f] hover:text-[#1e1e1c]">
                              <Upload className="h-3 w-3" />上传
                            </button>
                          </div>
                        </div>
                        <div className="space-y-0.5">
                          {screenshots.length === 0 ? (
                            <div className="rounded-md bg-[#f8f8f6] px-2 py-2 text-[10px] text-[#9a9a93]">暂无样本截图</div>
                          ) : (
                            screenshots.map((shot, shotIndex) => {
                              const active = activeScreenshotId === shot.id;
                              return (
                                <div
                                  key={shot.id || `${shot.name}-${shotIndex}`}
                                  onClick={() => onSelectScreenshot(classIndex, shot)}
                                  className={`group flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 ${
                                    active ? 'bg-[#edf8f1] text-emerald-800' : 'text-[#66665f] hover:bg-[#f4f4f1]'
                                  }`}
                                >
                                  <Camera className="h-3 w-3 shrink-0 text-emerald-600" />
                                  <span className="min-w-0 flex-1 truncate font-mono text-[9px]">{shot.name}</span>
                                  <button
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      onDeleteScreenshot(classIndex, shotIndex);
                                    }}
                                    className="rounded p-0.5 text-[#b1b1aa] opacity-0 hover:text-rose-600 group-hover:opacity-100"
                                    title="解除样本"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </div>
                              );
                            })
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </div>

      <Dialog
        open={isNewClassDialogOpen}
        onOpenChange={setIsNewClassDialogOpen}
        title="新建 UI 页面"
        description="类名会自动补全 UI 后缀。"
      >
        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-[11px] font-medium text-[#55554f]">类名</label>
            <Input
              autoFocus
              value={newClassName}
              onChange={(event) => setNewClassName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') createClass();
              }}
              placeholder="例如 Home"
              className="h-9 font-mono text-[11px]"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setIsNewClassDialogOpen(false)}>取消</Button>
            <Button onClick={createClass} disabled={!newClassName.trim()}>创建页面</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
