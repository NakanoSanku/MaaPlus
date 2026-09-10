import * as React from 'react';
import { Navbar } from './components/Navbar';
import { UIExplorer } from './components/UIExplorer';
import { ScreenCanvas } from './components/ScreenCanvas';
import { LocatorInspector } from './components/LocatorInspector';
import { DeviceController } from './components/DeviceController';
import { BacktestDashboard } from './components/BacktestDashboard';
import { CodePreview } from './components/CodePreview';
import {
  captureScreenshot,
  connectDevice,
  disconnectDevice,
  fetchDevices,
  fetchStatus,
  runClassBacktest,
  saveBoundScreenshot,
  saveTemplateImage,
  saveUIFile,
  scanProjectUI,
  sendKey,
  sendSwipe,
  sendTap,
  testRecognition,
} from './lib/api';
import {
  BoundScreenshot,
  ClassBacktestMatrixRow,
  ClassBacktestSummary,
  Device,
  LocatorConfig,
  RecognitionResult,
  UIClass,
} from './types';

// Default starter UI classes with sample bound screenshots
const INITIAL_UI_CLASSES: UIClass[] = [
  {
    name: 'HomeUI',
    locators: [
      {
        name: 'start_btn',
        type: 'Template',
        template: ['assets/image/start_btn.png'],
        threshold: 0.85,
        roi: [850, 480, 220, 80],
      },
      {
        name: 'settings_icon',
        type: 'Template',
        template: ['assets/image/settings.png'],
        threshold: 0.85,
        roi: [1200, 30, 60, 60],
      },
      {
        name: 'title_text',
        type: 'OCR',
        expected: ['作战终端', 'TERMINAL'],
        roi: [100, 30, 260, 60],
      },
    ],
    screenshots: [
      {
        id: 'home_standard_1080p',
        name: 'home_standard_1080p.png',
      },
    ],
  },
  {
    name: 'BattleUI',
    locators: [
      {
        name: 'pause_btn',
        type: 'Template',
        template: ['assets/image/pause.png'],
        threshold: 0.85,
        roi: [1210, 20, 55, 55],
      },
      {
        name: 'auto_battle_toggle',
        type: 'Template',
        template: ['assets/image/auto_battle.png'],
        threshold: 0.85,
        roi: [1120, 20, 60, 60],
      },
    ],
    screenshots: [
      {
        id: 'battle_stage_1',
        name: 'battle_stage_1.png',
      },
    ],
  },
];

export function App() {
  // Navigation & Tab state
  const [currentTab, setCurrentTab] = React.useState('canvas');

  // Backend & Device state
  const [backendOnline, setBackendOnline] = React.useState(false);
  const [devices, setDevices] = React.useState<Device[]>([]);
  const [selectedDevice, setSelectedDevice] = React.useState('offline');
  const [connectedDevice, setConnectedDevice] = React.useState<string | null>(null);

  // Screen & Capture state
  const [imageSrc, setImageSrc] = React.useState<string | null>(null);
  const [liveImageSrc, setLiveImageSrc] = React.useState<string | null>(null);
  const [imageDimensions, setImageDimensions] = React.useState({ width: 0, height: 0 });
  const [isCapturing, setIsCapturing] = React.useState(false);
  const [liveMonitor, setLiveMonitor] = React.useState(false);

  // Active viewing screenshot (if null, viewing live screen)
  const [activeScreenshot, setActiveScreenshot] = React.useState<BoundScreenshot | null>(null);

  // Multi-box overlay for backtest review
  const [multiRecognitionBoxes, setMultiRecognitionBoxes] = React.useState<
    Array<{
      name: string;
      hit: boolean;
      score?: number | null;
      box?: [number, number, number, number] | null;
    }>
  >([]);

  // UI Class & Locator state
  const [uiClasses, setUiClasses] = React.useState<UIClass[]>(() => {
    const saved = localStorage.getItem('maaplus_ui_classes');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      } catch {}
    }
    return INITIAL_UI_CLASSES;
  });
  const [selectedClassIndex, setSelectedClassIndex] = React.useState(0);
  const [selectedLocatorIndex, setSelectedLocatorIndex] = React.useState(0);
  const [isScanningUi, setIsScanningUi] = React.useState(false);

  // Recognition state
  const [recognitionResult, setRecognitionResult] = React.useState<RecognitionResult | null>(null);
  const [isRecognizing, setIsRecognizing] = React.useState(false);

  // Toast / notification
  const [toastMessage, setToastMessage] = React.useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // Sync uiClasses to localStorage
  React.useEffect(() => {
    localStorage.setItem('maaplus_ui_classes', JSON.stringify(uiClasses));
  }, [uiClasses]);

  // Check backend status & list devices
  const checkStatus = React.useCallback(async () => {
    try {
      const status = await fetchStatus();
      setBackendOnline(true);
      if (status.connected_device) {
        setConnectedDevice(status.connected_device.address);
        setSelectedDevice(status.connected_device.address);
      }
    } catch {
      setBackendOnline(false);
    }
  }, []);

  const refreshDevices = React.useCallback(async () => {
    try {
      const devs = await fetchDevices();
      setDevices(devs);
      if (devs.length > 0 && selectedDevice === 'offline') {
        setSelectedDevice(devs[0].address);
      }
    } catch (err) {
      console.warn('Devices refresh failed:', err);
    }
  }, [selectedDevice]);

  React.useEffect(() => {
    checkStatus();
    refreshDevices();
  }, [checkStatus, refreshDevices]);

  // Capture screenshot handler (from live device)
  const handleCaptureScreenshot = React.useCallback(async () => {
    setIsCapturing(true);
    try {
      const blob = await captureScreenshot();
      const url = URL.createObjectURL(blob);
      setImageSrc(url);
      setLiveImageSrc(url);
      setActiveScreenshot(null);
      setMultiRecognitionBoxes([]);

      // Measure dimensions
      const img = new Image();
      img.onload = () => {
        setImageDimensions({ width: img.width, height: img.height });
      };
      img.src = url;
    } catch (err: any) {
      showToast(`截图失败: ${err.message || '请检查设备连接'}`);
    } finally {
      setIsCapturing(false);
    }
  }, []);

  // Keyboard shortcut 'R' for screenshot
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.key === 'r' || e.key === 'R') &&
        !['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement).tagName)
      ) {
        e.preventDefault();
        handleCaptureScreenshot();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleCaptureScreenshot]);

  // Live Monitor Polling (1.5s interval)
  React.useEffect(() => {
    if (!liveMonitor) return;
    const interval = setInterval(() => {
      handleCaptureScreenshot();
    }, 1500);
    return () => clearInterval(interval);
  }, [liveMonitor, handleCaptureScreenshot]);

  // Device connect / disconnect
  const handleConnect = async () => {
    if (selectedDevice === 'offline') {
      setConnectedDevice('offline');
      showToast('已进入离线模拟模式');
      return;
    }
    showToast(`正在连接设备: ${selectedDevice}...`);
    try {
      const res = await connectDevice(selectedDevice);
      if (res.success) {
        setConnectedDevice(selectedDevice);
        showToast('设备连接成功！');
        handleCaptureScreenshot();
      } else {
        showToast(`连接失败: ${res.error || '未知错误'}`);
      }
    } catch (err: any) {
      showToast(`连接出错: ${err.message}`);
    }
  };

  const handleDisconnect = async () => {
    try {
      await disconnectDevice();
      setConnectedDevice(null);
      showToast('已断开设备连接');
    } catch (err: any) {
      showToast(`断开失败: ${err.message}`);
    }
  };

  // Open local screenshot file
  const handleOpenLocalImage = (file: File) => {
    const url = URL.createObjectURL(file);
    setImageSrc(url);
    setActiveScreenshot(null);
    setMultiRecognitionBoxes([]);
    const img = new Image();
    img.onload = () => {
      setImageDimensions({ width: img.width, height: img.height });
      showToast(`已加载图片: ${file.name} (${img.width}×${img.height})`);
    };
    img.src = url;
  };

  // Active UI class & locator helpers
  const activeClass = uiClasses[selectedClassIndex] || uiClasses[0];
  const activeLocator = activeClass ? activeClass.locators[selectedLocatorIndex] : null;

  // Locator update
  const handleUpdateLocator = (updated: LocatorConfig) => {
    setUiClasses((prev) => {
      const copy = [...prev];
      const targetClass = { ...copy[selectedClassIndex] };
      const locators = [...targetClass.locators];
      locators[selectedLocatorIndex] = updated;
      targetClass.locators = locators;
      copy[selectedClassIndex] = targetClass;
      return copy;
    });
  };

  // ROI selected on canvas
  const handleRoiSelected = (roi: [number, number, number, number]) => {
    if (!activeLocator) return;
    handleUpdateLocator({ ...activeLocator, roi });
  };

  // Touch tap on canvas
  const handleTouchTap = async (x: number, y: number) => {
    showToast(`点击坐标: (${x}, ${y})`);
    try {
      await sendTap(x, y);
      if (liveMonitor) {
        setTimeout(handleCaptureScreenshot, 300);
      }
    } catch (err: any) {
      showToast(`触控发送失败: ${err.message}`);
    }
  };

  // Hardware keys
  const handleSendKey = async (keycode: number) => {
    try {
      await sendKey(keycode);
      showToast(`按键发送: KeyCode ${keycode}`);
      if (liveMonitor) {
        setTimeout(handleCaptureScreenshot, 400);
      }
    } catch (err: any) {
      showToast(`按键发送失败: ${err.message}`);
    }
  };

  const handleSendSwipe = async (
    x1: number,
    y1: number,
    x2: number,
    y2: number,
    duration = 400
  ) => {
    try {
      await sendSwipe(x1, y1, x2, y2, duration);
      showToast(`滑动发送: (${x1},${y1}) → (${x2},${y2})`);
      if (liveMonitor) {
        setTimeout(handleCaptureScreenshot, 500);
      }
    } catch (err: any) {
      showToast(`滑动发送失败: ${err.message}`);
    }
  };

  // Test recognition
  const handleTestRecognition = async () => {
    if (!activeLocator) return;
    setIsRecognizing(true);
    setRecognitionResult(null);
    setMultiRecognitionBoxes([]);
    try {
      // Pass base64 image if available, or backend uses its current screenshot
      const res = await testRecognition(activeLocator);
      setRecognitionResult(res);
      if (res.hit) {
        showToast(`识别成功! 得分: ${res.score ? (res.score * 100).toFixed(1) + '%' : '匹配'}`);
      } else {
        showToast('未检测到目标');
      }
    } catch (err: any) {
      showToast(`识别请求出错: ${err.message}`);
    } finally {
      setIsRecognizing(false);
    }
  };

  // Save template image to backend project
  const handleSaveTemplateToProject = async (path: string, base64: string): Promise<boolean> => {
    try {
      const res = await saveTemplateImage(path, base64);
      if (res.success) {
        showToast(`模板已保存至 ${res.relative_path || path}`);
        return true;
      }
      showToast(`保存失败: ${res.error || '未知错误'}`);
      return false;
    } catch (err: any) {
      showToast(`保存出错: ${err.message}`);
      return false;
    }
  };

  // Scan project UI classes from Python files
  const handleScanProject = async () => {
    setIsScanningUi(true);
    try {
      const scanned = await scanProjectUI();
      if (scanned && scanned.length > 0) {
        setUiClasses(scanned);
        setSelectedClassIndex(0);
        setSelectedLocatorIndex(0);
        showToast(`成功从项目扫描到 ${scanned.length} 个 UI 类及关联样本！`);
      } else {
        showToast('未在项目中扫描到 UI 类，保持现有配置');
      }
    } catch (err: any) {
      showToast(`扫描失败: ${err.message}`);
    } finally {
      setIsScanningUi(false);
    }
  };

  // Save UI file code
  const handleSaveUiFile = async (filePath: string, code: string): Promise<boolean> => {
    try {
      const res = await saveUIFile(filePath, code);
      if (res.success) {
        showToast(`成功写入 ${filePath}`);
        return true;
      }
      showToast(`写入失败: ${res.error || '未知错误'}`);
      return false;
    } catch (err: any) {
      showToast(`写入出错: ${err.message}`);
      return false;
    }
  };

  // Switch to viewing a bound screenshot on canvas
  const handleSelectScreenshot = (classIdx: number, screenshot: BoundScreenshot) => {
    setSelectedClassIndex(classIdx);
    setActiveScreenshot(screenshot);
    setMultiRecognitionBoxes([]);
    setRecognitionResult(null);

    const src = screenshot.dataUrl || screenshot.path;
    if (src) {
      setImageSrc(src);
      const img = new Image();
      img.onload = () => {
        setImageDimensions({ width: img.width, height: img.height });
      };
      img.src = src;
    }
    showToast(`已载入样本「${screenshot.name}」到画布`);
  };

  // Return from screenshot inspection to live device feed
  const handleReturnToLive = () => {
    setActiveScreenshot(null);
    setMultiRecognitionBoxes([]);
    setRecognitionResult(null);
    if (liveImageSrc) {
      setImageSrc(liveImageSrc);
      const img = new Image();
      img.onload = () => {
        setImageDimensions({ width: img.width, height: img.height });
      };
      img.src = liveImageSrc;
      showToast('已返回实时画面');
    } else {
      handleCaptureScreenshot();
    }
  };

  // Bind current screen capture to the active UI class
  const handleBindCurrentScreenshot = async (classIdx: number) => {
    const targetClass = uiClasses[classIdx];
    if (!targetClass) return;
    if (!imageSrc) {
      showToast('当前画布无画面，请先截图或导入图片');
      return;
    }

    const currentCount = (targetClass.screenshots || []).length;
    const defaultName = `${targetClass.name.toLowerCase()}_sample_${currentCount + 1}.png`;
    const shotName = window.prompt('请输入该样本截图名称:', defaultName) || defaultName;

    // If backend online, save to disk
    let savedShot: BoundScreenshot = {
      id: shotName.replace(/\.[^/.]+$/, ''),
      name: shotName,
      dataUrl: imageSrc,
    };

    if (backendOnline) {
      try {
        const res = await saveBoundScreenshot(targetClass.name, shotName, imageSrc);
        if (res.success) {
          savedShot = {
            id: res.id || savedShot.id,
            name: res.name || savedShot.name,
            path: res.path,
            dataUrl: res.dataUrl || imageSrc,
          };
        }
      } catch (e) {
        console.warn('Failed saving bound screenshot to backend:', e);
      }
    }

    setUiClasses((prev) => {
      const copy = [...prev];
      const cls = { ...copy[classIdx] };
      cls.screenshots = [...(cls.screenshots || []), savedShot];
      copy[classIdx] = cls;
      return copy;
    });

    setActiveScreenshot(savedShot);
    showToast(`成功将当前画面绑定到「${targetClass.name}」！`);
  };

  // Upload an image file to bind to a UI class
  const handleUploadScreenshot = (classIdx: number, file: File) => {
    const targetClass = uiClasses[classIdx];
    if (!targetClass) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      const b64 = e.target?.result as string;
      let newShot: BoundScreenshot = {
        id: file.name.replace(/\.[^/.]+$/, ''),
        name: file.name,
        dataUrl: b64,
      };

      if (backendOnline) {
        try {
          const res = await saveBoundScreenshot(targetClass.name, file.name, b64);
          if (res.success) {
            newShot = {
              id: res.id || newShot.id,
              name: res.name || newShot.name,
              path: res.path,
              dataUrl: res.dataUrl || b64,
            };
          }
        } catch (err) {
          console.warn('Backend save bound screenshot failed:', err);
        }
      }

      setUiClasses((prev) => {
        const copy = [...prev];
        const cls = { ...copy[classIdx] };
        cls.screenshots = [...(cls.screenshots || []), newShot];
        copy[classIdx] = cls;
        return copy;
      });

      handleSelectScreenshot(classIdx, newShot);
      showToast(`已绑定样本「${file.name}」至「${targetClass.name}」`);
    };
    reader.readAsDataURL(file);
  };

  // Delete a bound screenshot
  const handleDeleteScreenshot = (classIdx: number, shotIdx: number) => {
    setUiClasses((prev) => {
      const copy = [...prev];
      const cls = { ...copy[classIdx] };
      const shots = [...(cls.screenshots || [])];
      shots.splice(shotIdx, 1);
      cls.screenshots = shots;
      copy[classIdx] = cls;
      return copy;
    });
    if (activeScreenshot) {
      handleReturnToLive();
    }
    showToast('已解除样本截图绑定');
  };

  // Execute Class Backtest
  const handleRunClassBacktest = async (uiClass: UIClass): Promise<ClassBacktestSummary> => {
    return runClassBacktest({
      ui_class: uiClass.name,
      locators: uiClass.locators,
      screenshots: uiClass.screenshots || [],
    });
  };

  // Inspect backtest row result on canvas
  const handleInspectScreenshotOnCanvas = (
    screenshot: BoundScreenshot,
    rowResult?: ClassBacktestMatrixRow
  ) => {
    handleSelectScreenshot(selectedClassIndex, screenshot);

    if (rowResult) {
      const boxes: Array<{
        name: string;
        hit: boolean;
        score?: number | null;
        box?: [number, number, number, number] | null;
      }> = [];

      for (const [locName, res] of Object.entries(rowResult.results)) {
        if (res.box) {
          boxes.push({
            name: locName,
            hit: res.hit,
            score: res.score,
            box: res.box,
          });
        }
      }
      setMultiRecognitionBoxes(boxes);
    }

    setCurrentTab('canvas');
    showToast(`已在画布中呈现「${screenshot.name}」全元素匹配结果`);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans select-none">
      {/* Navbar */}
      <Navbar
        backendOnline={backendOnline}
        devices={devices}
        selectedDevice={selectedDevice}
        onSelectDevice={setSelectedDevice}
        onRefreshDevices={refreshDevices}
        connectedDevice={connectedDevice}
        onConnectDevice={handleConnect}
        onDisconnectDevice={handleDisconnect}
        onCaptureScreenshot={handleCaptureScreenshot}
        isCapturing={isCapturing}
        liveMonitor={liveMonitor}
        onToggleLiveMonitor={() => setLiveMonitor(!liveMonitor)}
        onOpenLocalImage={handleOpenLocalImage}
        currentTab={currentTab}
        onTabChange={setCurrentTab}
      />

      {/* Main Tab Views */}
      <div className="flex-1 flex overflow-hidden relative">
        {currentTab === 'canvas' && (
          <>
            {/* Left: UI Explorer (Classes, Locators, & Bound Screenshots Tree) */}
            <div className="w-72 shrink-0 h-full">
              <UIExplorer
                uiClasses={uiClasses}
                selectedClassIndex={selectedClassIndex}
                selectedLocatorIndex={selectedLocatorIndex}
                activeScreenshotId={activeScreenshot?.id || null}
                onSelectClass={(idx) => {
                  setSelectedClassIndex(idx);
                  setSelectedLocatorIndex(0);
                  setRecognitionResult(null);
                  setMultiRecognitionBoxes([]);
                }}
                onSelectLocator={(cIdx, lIdx) => {
                  setSelectedClassIndex(cIdx);
                  setSelectedLocatorIndex(lIdx);
                  setRecognitionResult(null);
                }}
                onSelectScreenshot={handleSelectScreenshot}
                onAddClass={(name) => {
                  setUiClasses((prev) => [...prev, { name, locators: [], screenshots: [] }]);
                  setSelectedClassIndex(uiClasses.length);
                  setSelectedLocatorIndex(0);
                }}
                onDeleteClass={(idx) => {
                  setUiClasses((prev) => prev.filter((_, i) => i !== idx));
                  setSelectedClassIndex(Math.max(0, idx - 1));
                  setSelectedLocatorIndex(0);
                }}
                onAddLocator={(cIdx, loc) => {
                  setUiClasses((prev) => {
                    const copy = [...prev];
                    copy[cIdx] = {
                      ...copy[cIdx],
                      locators: [...copy[cIdx].locators, loc],
                    };
                    return copy;
                  });
                  setSelectedLocatorIndex(uiClasses[cIdx].locators.length);
                }}
                onDeleteLocator={(cIdx, lIdx) => {
                  setUiClasses((prev) => {
                    const copy = [...prev];
                    copy[cIdx] = {
                      ...copy[cIdx],
                      locators: copy[cIdx].locators.filter((_, i) => i !== lIdx),
                    };
                    return copy;
                  });
                  setSelectedLocatorIndex(Math.max(0, lIdx - 1));
                }}
                onBindCurrentScreenshot={handleBindCurrentScreenshot}
                onUploadScreenshot={handleUploadScreenshot}
                onDeleteScreenshot={handleDeleteScreenshot}
                onScanProject={handleScanProject}
                isScanning={isScanningUi}
              />
            </div>

            {/* Center: Interactive Canvas & Device Bar */}
            <div className="flex-1 flex flex-col h-full overflow-hidden">
              <ScreenCanvas
                imageSrc={imageSrc}
                imageDimensions={imageDimensions}
                activeLocator={activeLocator}
                allLocators={activeClass ? activeClass.locators : []}
                recognitionResult={recognitionResult}
                multiRecognitionBoxes={multiRecognitionBoxes}
                activeScreenshotName={activeScreenshot?.name || null}
                onReturnToLive={handleReturnToLive}
                onRoiSelected={handleRoiSelected}
                onTouchTap={handleTouchTap}
                className="flex-1"
              />
              <DeviceController
                connectedDevice={connectedDevice}
                onSendKey={handleSendKey}
                onSendTap={handleTouchTap}
                onSendSwipe={handleSendSwipe}
              />
            </div>

            {/* Right: Locator Inspector */}
            <div className="w-84 shrink-0 h-full">
              <LocatorInspector
                locator={activeLocator}
                className={activeClass?.name || ''}
                imageSrc={imageSrc}
                recognitionResult={recognitionResult}
                isRecognizing={isRecognizing}
                onUpdateLocator={handleUpdateLocator}
                onTestRecognition={handleTestRecognition}
                onSaveTemplateToProject={handleSaveTemplateToProject}
                onTapCoordinate={handleTouchTap}
              />
            </div>
          </>
        )}

        {currentTab === 'backtest' && (
          <BacktestDashboard
            uiClasses={uiClasses}
            selectedClassIndex={selectedClassIndex}
            onSelectClassIndex={(idx) => {
              setSelectedClassIndex(idx);
              setSelectedLocatorIndex(0);
            }}
            onRunClassBacktest={handleRunClassBacktest}
            onInspectScreenshotOnCanvas={handleInspectScreenshotOnCanvas}
            onBindCurrentScreenshot={handleBindCurrentScreenshot}
            onUploadScreenshot={handleUploadScreenshot}
          />
        )}

        {currentTab === 'code' && (
          <CodePreview
            uiClasses={uiClasses}
            selectedClassIndex={selectedClassIndex}
            onSaveUiFile={handleSaveUiFile}
            onImportClasses={(classes) => {
              setUiClasses(classes);
              setSelectedClassIndex(0);
              setSelectedLocatorIndex(0);
            }}
          />
        )}
      </div>

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-12 right-6 z-50 bg-slate-900/95 border border-sky-500/50 text-sky-200 text-xs px-4 py-2.5 rounded-lg shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-2 duration-150 flex items-center space-x-2">
          <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
