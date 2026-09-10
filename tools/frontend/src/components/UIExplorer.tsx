import * as React from 'react';
import {
  FolderTree,
  Plus,
  Search,
  Trash2,
  Image as ImageIcon,
  Type,
  ChevronRight,
  ChevronDown,
  Layers,
  Camera,
  Upload,
  Eye,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
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
  const [expandedClasses, setExpandedClasses] = React.useState<Record<string, boolean>>({
    '0': true,
  });
  const [isNewClassDialogOpen, setIsNewClassDialogOpen] = React.useState(false);
  const [newClassName, setNewClassName] = React.useState('');

  const uploadInputRef = React.useRef<HTMLInputElement>(null);
  const [targetClassForUpload, setTargetClassForUpload] = React.useState<number>(0);

  const toggleExpand = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedClasses((prev) => ({
      ...prev,
      [index.toString()]: !prev[index.toString()],
    }));
  };

  const handleCreateClass = () => {
    const trimmed = newClassName.trim();
    if (!trimmed) return;
    const name = trimmed.endsWith('UI') ? trimmed : `${trimmed}UI`;
    onAddClass(name);
    setNewClassName('');
    setIsNewClassDialogOpen(false);
  };

  const handleAddDefaultLocator = (classIdx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    const targetClass = uiClasses[classIdx];
    const newName = `target_btn_${targetClass.locators.length + 1}`;
    const newLoc: LocatorConfig = {
      name: newName,
      type: 'Template',
      template: [`assets/image/${newName}.png`],
      threshold: 0.85,
      roi: null,
    };
    onAddLocator(classIdx, newLoc);
    setExpandedClasses((prev) => ({ ...prev, [classIdx.toString()]: true }));
  };

  const triggerUpload = (classIdx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setTargetClassForUpload(classIdx);
    uploadInputRef.current?.click();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUploadScreenshot(targetClassForUpload, e.target.files[0]);
      e.target.value = '';
    }
  };

  const filteredClasses = uiClasses
    .map((cls, classIndex) => {
      const matchClass = cls.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchedLocators = cls.locators.filter((loc) =>
        loc.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
      return {
        cls,
        classIndex,
        matchClass,
        matchedLocators,
        visible: matchClass || matchedLocators.length > 0,
      };
    })
    .filter((item) => item.visible);

  return (
    <div className="flex flex-col h-full bg-slate-900/60 border-r border-slate-800 select-none">
      {/* Hidden File Input for uploading bound screenshots */}
      <input
        type="file"
        ref={uploadInputRef}
        onChange={handleFileInputChange}
        accept="image/*"
        className="hidden"
      />

      {/* Header */}
      <div className="p-3 border-b border-slate-800 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-200">
            <FolderTree className="w-4 h-4 text-sky-400" />
            <span>UI 页面类 (UI Classes)</span>
            <Badge variant="outline" className="text-[10px] px-1 py-0 border-slate-700 text-slate-400">
              {uiClasses.length}
            </Badge>
          </div>
          <div className="flex items-center space-x-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={onScanProject}
              disabled={isScanning}
              className="h-7 w-7 p-0 text-slate-400 hover:text-sky-400"
              title="扫描项目源码中的 UI 类及关联样本"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              size="sm"
              onClick={() => setIsNewClassDialogOpen(true)}
              className="h-7 px-2 text-xs bg-sky-600/90 hover:bg-sky-500 text-white"
              title="新建 UI 类"
            >
              <Plus className="w-3.5 h-3.5 mr-1" />
              <span>新建类</span>
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
          <Input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="搜索 UI 类或定位符..."
            className="pl-8 h-8 text-xs bg-slate-950/60 border-slate-800 focus:border-sky-500/50"
          />
        </div>
      </div>

      {/* Tree Content */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {filteredClasses.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center p-4">
            <Layers className="w-8 h-8 text-slate-600 mb-2" />
            <p className="text-xs text-slate-400">暂无匹配的 UI 类</p>
            <p className="text-[11px] text-slate-600 mt-1">点击上方“新建类”或“扫描项目”</p>
          </div>
        ) : (
          filteredClasses.map(({ cls, classIndex }) => {
            const isExpanded = expandedClasses[classIndex.toString()] ?? true;
            const isClassSelected = selectedClassIndex === classIndex;
            const screenshots = cls.screenshots || [];

            return (
              <div
                key={cls.name + classIndex}
                className={`space-y-0.5 rounded-lg border transition-all overflow-hidden ${
                  isClassSelected
                    ? 'border-sky-500/40 bg-slate-900/80 shadow-xs shadow-sky-950/20'
                    : 'border-slate-800/50 bg-slate-950/30'
                }`}
              >
                {/* Class Row */}
                <div
                  onClick={() => onSelectClass(classIndex)}
                  className={`flex items-center justify-between px-2.5 py-2 rounded cursor-pointer transition-colors group ${
                    isClassSelected
                      ? 'bg-sky-950/30 text-sky-200 font-semibold'
                      : 'text-slate-300 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="flex items-center space-x-1.5 min-w-0">
                    <button
                      onClick={(e) => toggleExpand(classIndex, e)}
                      className="p-0.5 rounded text-slate-500 hover:text-slate-200"
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5" />
                      )}
                    </button>
                    <span className="text-xs truncate">{cls.name}</span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      ({cls.locators.length} 元素 · {screenshots.length} 截图)
                    </span>
                  </div>

                  <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {uiClasses.length > 1 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteClass(classIndex);
                        }}
                        className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800"
                        title="删除此类"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Sub-tree: Locators & Bound Screenshots */}
                {isExpanded && (
                  <div className="px-2.5 pb-2.5 pt-1 space-y-2 text-xs">
                    {/* SECTION 1: LOCATORS */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium px-1">
                        <span className="flex items-center space-x-1">
                          <span>元素定位符 ({cls.locators.length})</span>
                        </span>
                        <button
                          onClick={(e) => handleAddDefaultLocator(classIndex, e)}
                          className="flex items-center space-x-0.5 text-[10px] text-sky-400 hover:text-sky-300 transition-colors"
                          title="添加定位符"
                        >
                          <Plus className="w-3 h-3" />
                          <span>添加</span>
                        </button>
                      </div>

                      <div className="space-y-0.5 pl-1.5 border-l border-slate-800/80">
                        {cls.locators.length === 0 ? (
                          <div className="text-[10px] text-slate-600 italic py-0.5 pl-1">
                            暂无定位符
                          </div>
                        ) : (
                          cls.locators.map((loc, locIndex) => {
                            const isLocSelected =
                              isClassSelected && selectedLocatorIndex === locIndex;

                            return (
                              <div
                                key={loc.name + locIndex}
                                onClick={() => onSelectLocator(classIndex, locIndex)}
                                className={`flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-colors group ${
                                  isLocSelected
                                    ? 'bg-sky-500/20 text-sky-200 font-semibold'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                                }`}
                              >
                                <div className="flex items-center space-x-1.5 truncate">
                                  {loc.type === 'Template' ? (
                                    <ImageIcon className="w-3 h-3 text-sky-400 shrink-0" />
                                  ) : (
                                    <Type className="w-3 h-3 text-emerald-400 shrink-0" />
                                  )}
                                  <span className="truncate font-mono text-[11px]">{loc.name}</span>
                                </div>

                                <div className="flex items-center space-x-1 shrink-0">
                                  {loc.roi && (
                                    <span className="text-[9px] px-1 py-0 rounded bg-slate-800 text-slate-400 font-mono">
                                      ROI
                                    </span>
                                  )}
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onDeleteLocator(classIndex, locIndex);
                                    }}
                                    className="p-0.5 rounded text-slate-600 hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                    title="删除定位符"
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </button>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>

                    {/* SECTION 2: BOUND SCREENSHOTS (1-to-N Relationship) */}
                    <div className="space-y-1 pt-1 border-t border-slate-800/50">
                      <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium px-1">
                        <span className="flex items-center space-x-1">
                          <span>绑定样本截图 ({screenshots.length})</span>
                        </span>
                        <div className="flex items-center space-x-1.5">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              onBindCurrentScreenshot(classIndex);
                            }}
                            className="flex items-center space-x-0.5 text-[10px] text-emerald-400 hover:text-emerald-300 transition-colors"
                            title="将画布当前画面绑定为该 UI 类的测试样本"
                          >
                            <Camera className="w-3 h-3" />
                            <span>绑定当前</span>
                          </button>
                          <button
                            onClick={(e) => triggerUpload(classIndex, e)}
                            className="flex items-center space-x-0.5 text-[10px] text-indigo-400 hover:text-indigo-300 transition-colors"
                            title="上传本地图片作为样本截图"
                          >
                            <Upload className="w-3 h-3" />
                            <span>上传</span>
                          </button>
                        </div>
                      </div>

                      <div className="space-y-0.5 pl-1.5 border-l border-emerald-500/20">
                        {screenshots.length === 0 ? (
                          <div className="text-[10px] text-slate-600 italic py-0.5 pl-1">
                            未绑定截图，点击「绑定当前」或「上传」
                          </div>
                        ) : (
                          screenshots.map((shot, shotIndex) => {
                            const isShotActive = activeScreenshotId === shot.id;

                            return (
                              <div
                                key={shot.id || shot.name + shotIndex}
                                onClick={() => onSelectScreenshot(classIndex, shot)}
                                className={`flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-colors group ${
                                  isShotActive
                                    ? 'bg-emerald-500/20 text-emerald-300 font-medium border border-emerald-500/30'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                                }`}
                                title="点击载入画布进行查看与验证"
                              >
                                <div className="flex items-center space-x-1.5 truncate">
                                  {shot.dataUrl ? (
                                    <img
                                      src={shot.dataUrl}
                                      alt={shot.name}
                                      className="w-4 h-3 object-cover rounded shrink-0 border border-slate-700"
                                    />
                                  ) : (
                                    <Camera className="w-3 h-3 text-emerald-400 shrink-0" />
                                  )}
                                  <span className="truncate font-mono text-[11px]">{shot.name}</span>
                                </div>

                                <div className="flex items-center space-x-1 shrink-0">
                                  {isShotActive && (
                                    <span className="text-[9px] px-1 py-0 rounded bg-emerald-500/20 text-emerald-400 font-mono">
                                      当前查看
                                    </span>
                                  )}
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      onDeleteScreenshot(classIndex, shotIndex);
                                    }}
                                    className="p-0.5 rounded text-slate-600 hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                    title="解除此截图绑定"
                                  >
                                    <Trash2 className="w-3 h-3" />
                                  </button>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* New UI Class Dialog */}
      <Dialog
        open={isNewClassDialogOpen}
        onOpenChange={setIsNewClassDialogOpen}
        title="新建 UI 页面类"
        description="创建一个继承自 UI 的页面类，例如 HomeUI, BattleUI, InventoryUI"
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-slate-300">类名 (PascalCase)</label>
            <Input
              value={newClassName}
              onChange={(e) => setNewClassName(e.target.value)}
              placeholder="例如：HomeUI, BattleUI"
              className="mt-1"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleCreateClass();
              }}
            />
          </div>
          <div className="flex justify-end space-x-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsNewClassDialogOpen(false)}
            >
              取消
            </Button>
            <Button
              size="sm"
              onClick={handleCreateClass}
              className="bg-sky-600 hover:bg-sky-500 text-white"
            >
              创建
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
