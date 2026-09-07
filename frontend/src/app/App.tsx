import { useState, useRef, useEffect } from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import * as Dialog from '@radix-ui/react-dialog';
import * as Slider from '@radix-ui/react-slider';
import NiivueViewer, { SliceType, DragMode } from './NiivueViewer';
import * as Select from '@radix-ui/react-select';
import { Brain, FileText, HelpCircle, Upload, Download, Info, Activity, ChevronDown, Languages } from 'lucide-react';

import { Language, translations } from './translations';
import { exportReportAsPDF, generateClinicalInterpretation, AnalysisData } from './reportGenerator';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

enum TaskStatus {
  STARTED = 0,
  PENDING = 1,
  DONE = 2,
}

export default function App() {
  const [showImportModal, setShowImportModal] = useState(false);
  const [showAgeModal, setShowAgeModal] = useState(false);
  const [selectedTab, setSelectedTab] = useState('home');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedFileObj, setSelectedFileObj] = useState<File | null>(null);
  const [age, setAge] = useState('');
  const [language, setLanguage] = useState<Language>('en');
  const [sliceType, setSliceType] = useState<SliceType>('multi');
  const [dragMode, setDragMode] = useState<DragMode>('zoom');
  const [azimuth, setAzimuth] = useState(110);
  const [elevation, setElevation] = useState(15);

  // Backend integration states
  const [mriUrl, setMriUrl] = useState<string | null>(null);
  const [maskUrl, setMaskUrl] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState('');
  const [analysisResults, setAnalysisResults] = useState<AnalysisData | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  const t = translations[language];

  // Fetch history on startup
  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/tasks`);
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (e) {
      console.error("Failed to fetch history", e);
    }
  };

  const handleTabChange = (value: string) => {
    setSelectedTab(value);
    if (value === 'analysis' && !selectedFile && !mriUrl) {
      setShowImportModal(true);
    }
  };

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelectClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file.name);
      setSelectedFileObj(file);
      setShowImportModal(false);
      setShowAgeModal(true);
    }
  };

  const pollTaskStatus = (taskId: string, ws: WebSocket) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/tasks/${taskId}`);
        if (!res.ok) {
          clearInterval(interval);
          setIsAnalyzing(false);
          return;
        }

        const task = await res.json();
        if (task.status === TaskStatus.PENDING) {
          setAnalysisProgress('Running pipeline (Preprocessing -> Registration -> Atlas HarP -> Volumetry)...');
        } else if (task.status === TaskStatus.DONE) {
          clearInterval(interval);
          setIsAnalyzing(false);
          setAnalysisResults({
            left_volume:  task.left_volume,
            right_volume: task.right_volume,
            total_volume: task.total_volume,
            brain_volume: task.brain_volume !== undefined ? task.brain_volume : undefined,
            asymmetry_index: task.asymmetry_index,
            dice_left: task.dice_left,
            dice_right: task.dice_right,
            iou_left: task.iou_left,
            iou_right: task.iou_right,
            classification_left: task.classification_left,
            classification_right: task.classification_right,
            status_text: task.status_text,
          });
          setMaskUrl(`${API_BASE_URL}/tasks/${taskId}/mask`);
          fetchHistory();
          ws.close();
          return;
        } else {
          clearInterval(interval);
          setIsAnalyzing(false);
          alert('Analysis pipeline failed on the server.');
          return;
        }
      } catch (err) {
        console.error('Error polling status', err);
        clearInterval(interval);
        setIsAnalyzing(false);
        return;
      }
    }, 1000);
  };

  const handleWebSocketMessage = async (taskId: string, event: any) => {
    const task = JSON.parse(event.data);
    if (task.task_id !== taskId) {
      console.error("Task ID incorrect");
      return;
    }

    switch (task.status) {
      case (TaskStatus.DONE):
        setIsAnalyzing(false);
        setAnalysisResults({
          left_volume:  task.left_volume,
          right_volume: task.right_volume,
          total_volume: task.total_volume,
          brain_volume: task.brain_volume !== undefined ? task.brain_volume : undefined,
          asymmetry_index: task.asymmetry_index,
          dice_left: task.dice_left,
          dice_right: task.dice_right,
          iou_left: task.iou_left,
          iou_right: task.iou_right,
          classification_left: task.classification_left,
          classification_right: task.classification_right,
          status_text: task.status_text,
        });
        setMaskUrl(`${API_BASE_URL}/tasks/${taskId}/mask`);
        fetchHistory();
        break;
      default:
        setIsAnalyzing(false);
        alert('Analysis pipeline failed on the server.');
        break;
    }
    console.log("Task update:", task);
  }

  const handleAgeConfirm = async () => {
    setShowAgeModal(false);
    if (!selectedFileObj || !age) return;

    setIsAnalyzing(true);
    setAnalysisProgress('Uploading scan to server...');
    setAnalysisResults(null);
    setMriUrl(null);
    setMaskUrl(null);

    const formData = new FormData();
    formData.append('file', selectedFileObj);
    formData.append('age', age);

    try {
      const res = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        throw new Error('Failed to initiate analysis');
      }

      const task = await res.json();
      const taskId = task.task_id;
      
      setMriUrl(`${API_BASE_URL}/tasks/${taskId}/mri`);
      setAnalysisProgress('Running pipeline (Preprocessing -> Registration -> Atlas HarP -> Volumetry)...');
      const ws = new WebSocket("ws");

      ws.onmessage = (event) => {
        handleWebSocketMessage(taskId, event);
        ws.close();
      };

      ws.onopen = () => {
        console.log("Web socket successfully connected.");
      };

      ws.onclose = (e) => {
        console.log("WS closed", e.code, e.reason);
      };
      
      ws.onerror = (e) => {
        console.log("WS error", e);
      };

      pollTaskStatus(taskId, ws);
    } catch (err) {
      console.error(err);
      setIsAnalyzing(false);
      alert('Error: Could not connect to backend. Please ensure the backend server is running on port 8000.');
    }
  };

  const handleSelectHistoryTask = (task: any) => {
    setSelectedFile(task.filename);
    setSelectedFileObj(null); // Clear local file to use backend URLs
    setAge(task.age.toString());
    setMriUrl(`${API_BASE_URL}/tasks/${task.task_id}/mri`);
    if (task.status === 'completed') {
      setMaskUrl(`${API_BASE_URL}/tasks/${task.task_id}/mask`);
      setAnalysisResults({
        left_volume:  task.left_volume,
        right_volume: task.right_volume,
        total_volume: task.total_volume,
        brain_volume: task.brain_volume !== undefined ? task.brain_volume : undefined,
        asymmetry_index: task.asymmetry_index,
        dice_left: task.dice_left,
        dice_right: task.dice_right,
        iou_left: task.iou_left,
        iou_right: task.iou_right,
        classification_left: task.classification_left,
        classification_right: task.classification_right,
        status_text: task.status_text,
      });
    } else {
      setMaskUrl(null);
      setAnalysisResults(null);
    }
  };

  const handleAgeChange = (val: string) => {
    if (val === '') {
      setAge('');
      return;
    }
    const num = Number(val);
    if (!isNaN(num)) {
      setAge(Math.abs(num).toString());
    }
  };

  return (
    <div className="size-full bg-neutral-50">
      <Tabs.Root value={selectedTab} onValueChange={handleTabChange} className="size-full flex flex-col">
        {/* Tab Navigation */}
        <Tabs.List className="flex border-b border-neutral-200 bg-white px-8">
          <Tabs.Trigger
            value="home"
            className="px-8 py-4 text-neutral-600 hover:text-neutral-900 data-[state=active]:text-[#6b7c59] data-[state=active]:border-b-2 data-[state=active]:border-[#6b7c59] transition-colors"
          >
            {t.tabHome}
          </Tabs.Trigger>
          <Tabs.Trigger
            value="analysis"
            className="px-8 py-4 text-neutral-600 hover:text-neutral-900 data-[state=active]:text-[#6b7c59] data-[state=active]:border-b-2 data-[state=active]:border-[#6b7c59] transition-colors"
          >
            {t.tabAnalysis}
          </Tabs.Trigger>

          {/* Language Selector */}
          <div className="ml-auto flex items-center">
            <Select.Root value={language} onValueChange={(value) => setLanguage(value as Language)}>
              <Select.Trigger className="flex items-center gap-2 px-4 py-2 text-neutral-600 hover:text-neutral-900 transition-colors">
                <Languages className="w-4 h-4" />
                <span className="uppercase">{language}</span>
                <ChevronDown className="w-4 h-4" />
              </Select.Trigger>
              <Select.Portal>
                <Select.Content position="popper" sideOffset={4} className="z-50 min-w-[8rem] bg-white rounded-xl shadow-lg border border-neutral-200 overflow-hidden">
                  <Select.Viewport className="p-1">
                    <Select.Item value="en" className="px-4 py-2 text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded-lg outline-none">
                      <Select.ItemText>English</Select.ItemText>
                    </Select.Item>
                    <Select.Item value="fr" className="px-4 py-2 text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded-lg outline-none">
                      <Select.ItemText>Français</Select.ItemText>
                    </Select.Item>
                    <Select.Item value="es" className="px-4 py-2 text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded-lg outline-none">
                      <Select.ItemText>Español</Select.ItemText>
                    </Select.Item>
                  </Select.Viewport>
                </Select.Content>
              </Select.Portal>
            </Select.Root>
          </div>
        </Tabs.List>

        {/* Home Tab Content */}
        <Tabs.Content value="home" className="flex-1 overflow-auto">
          <div className="max-w-5xl mx-auto p-12">
            {/* Header */}
            <div className="mb-12">
              <div className="flex items-center gap-4 mb-4">
                <Brain className="w-12 h-12 text-[#6b7c59]" />
                <h1 className="text-4xl text-neutral-900">{t.appName}</h1>
              </div>
              <p className="text-xl text-neutral-600">
                {t.tagline}
              </p>
            </div>

            {/* What is NeuroVolumetry */}
            <section className="mb-10 bg-white rounded-2xl p-8 shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <Info className="w-6 h-6 text-[#6b7c59]" />
                <h2 className="text-2xl text-neutral-900">{t.whatIsTitle}</h2>
              </div>
              <p className="text-neutral-700 mb-4">
                {t.whatIsText1}
              </p>
              <p className="text-neutral-700">
                {t.whatIsText2}
              </p>
            </section>

            {/* How the Analysis Works */}
            <section className="mb-10 bg-white rounded-2xl p-8 shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <Activity className="w-6 h-6 text-[#6b7c59]" />
                <h2 className="text-2xl text-neutral-900">{t.howWorksTitle}</h2>
              </div>
              <div className="space-y-4">
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#6b7c59] text-white flex items-center justify-center">1</div>
                  <div>
                    <h3 className="text-lg text-neutral-900 mb-1">{t.step1Title}</h3>
                    <p className="text-neutral-700">
                      {t.step1Text}
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#6b7c59] text-white flex items-center justify-center">2</div>
                  <div>
                    <h3 className="text-lg text-neutral-900 mb-1">{t.step2Title}</h3>
                    <p className="text-neutral-700">
                      {t.step2Text}
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#6b7c59] text-white flex items-center justify-center">3</div>
                  <div>
                    <h3 className="text-lg text-neutral-900 mb-1">{t.step3Title}</h3>
                    <p className="text-neutral-700">
                      {t.step3Text}
                    </p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[#6b7c59] text-white flex items-center justify-center">4</div>
                  <div>
                    <h3 className="text-lg text-neutral-900 mb-1">{t.step4Title}</h3>
                    <p className="text-neutral-700">
                      {t.step4Text}
                    </p>
                  </div>
                </div>
              </div>
            </section>

            {/* Understanding Alzheimer's Disease */}
            <section className="bg-white rounded-2xl p-8 shadow-sm">
              <div className="flex items-center gap-3 mb-4">
                <FileText className="w-6 h-6 text-[#6b7c59]" />
                <h2 className="text-2xl text-neutral-900">{t.alzheimerTitle}</h2>
              </div>
              <p className="text-neutral-700 mb-4">
                {t.alzheimerIntro}
              </p>
              <h3 className="text-lg text-neutral-900 mb-2">{t.keyCharacteristics}</h3>
              <ul className="space-y-2 mb-4 ml-5">
                <li className="text-neutral-700">
                  {t.char1}
                </li>
                <li className="text-neutral-700">
                  {t.char2}
                </li>
                <li className="text-neutral-700">
                  {t.char3}
                </li>
              </ul>
              <h3 className="text-lg text-neutral-900 mb-2">{t.hippocampalRole}</h3>
              <p className="text-neutral-700 mb-4">
                {t.hippocampalText}
              </p>
              <div className="bg-[#6b7c59]/5 border border-[#6b7c59]/20 rounded-xl p-6">
                <p className="text-neutral-700">
                  <strong>{t.noteLabel}</strong> {t.noteText}
                </p>
              </div>
            </section>
          </div>
        </Tabs.Content>

        {/* Analysis Tab Content */}
        <Tabs.Content value="analysis" className="flex-1 flex overflow-hidden">
          {/* Left Sidebar */}
          <div className="w-80 bg-[#6b7c59] text-white flex flex-col p-6">
            {/* Title */}
            <div className="mb-8">
              <h1 className="text-2xl">{t.appName}</h1>
            </div>

            {/* Help Panel */}
            <div className="bg-neutral-100 text-neutral-800 rounded-xl p-4 mb-6">
              <div className="flex items-center gap-2 mb-2">
                <HelpCircle className="w-5 h-5 text-[#6b7c59]" />
                <h3 className="font-medium">{t.help}</h3>
              </div>
              <p className="text-sm text-neutral-600">
                {t.helpText}
              </p>
            </div>

            {/* File Selection */}
            <div className="mb-6">
              <button
                onClick={() => setShowImportModal(true)}
                className="w-full bg-white text-[#6b7c59] rounded-xl px-4 py-3 flex items-center justify-center gap-2 hover:bg-neutral-50 transition-colors font-medium shadow-sm"
              >
                <Upload className="w-5 h-5" />
                {t.selectFile}
              </button>
              {selectedFile && (
                <p className="text-sm mt-2 text-white/80">{t.selectedFile} <span className="font-semibold block truncate">{selectedFile}</span></p>
              )}
            </div>

            {/* Age Input */}
            <div className="mb-6">
              <label className="block text-sm mb-2">{t.enterAge}</label>
              <input
                type="number"
                min="0"
                value={age}
                onChange={(e) => handleAgeChange(e.target.value)}
                placeholder={t.patientAge}
                className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-2 text-white placeholder:text-white/50 focus:outline-none focus:ring-2 focus:ring-white/30"
              />
            </div>

            {/* Recent Analyses History */}
            <div className="flex-1 overflow-y-auto mb-6 pr-1 border-t border-white/20 pt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white/70 mb-3">Recent Analyses</h3>
              {history.length === 0 ? (
                <p className="text-xs text-white/50 italic">No history found</p>
              ) : (
                <div className="space-y-2">
                  {history.map((task) => (
                    <button
                      key={task.task_id}
                      onClick={() => handleSelectHistoryTask(task)}
                      className={`w-full text-left rounded-xl p-3 transition-all border text-xs ${
                        selectedFile === task.filename 
                          ? 'bg-white/20 border-white/40 shadow-sm' 
                          : 'bg-white/5 hover:bg-white/10 border-white/10 hover:border-white/20'
                      }`}
                    >
                      <div className="font-semibold truncate text-white">{task.filename}</div>
                      <div className="flex justify-between mt-1 text-white/60">
                        <span>Age: {task.age}</span>
                        <span className="capitalize">{task.status}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Export Button */}
            <button 
              onClick={() => {
                if (!analysisResults) {
                  alert("No analysis results to export yet. Please run an analysis first.");
                  return;
                }
                const ageNum = parseInt(age, 10) || 0;
                exportReportAsPDF(
                  analysisResults as AnalysisData,
                  ageNum,
                  selectedFile ?? 'scan.nii.gz'
                );
              }}
              className="w-full bg-white/10 border border-white/20 text-white rounded-xl px-4 py-3 flex items-center justify-center gap-2 hover:bg-white/20 transition-colors font-medium"
            >
              <Download className="w-5 h-5" />
              {t.exportReport}
            </button>
          </div>

          {/* Main Content Area */}
          <div className="flex-1 bg-white p-8 overflow-auto">
            <div className="max-w-4xl mx-auto">
              {/* Image Area */}
              <div className="bg-black rounded-2xl aspect-[16/10] mb-6 flex items-center justify-center relative overflow-hidden shadow-inner border border-neutral-200">
                {isAnalyzing && (
                  <div className="absolute inset-0 bg-black/75 z-10 flex flex-col items-center justify-center p-6 text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white mb-4"></div>
                    <p className="text-white font-medium text-lg">Running Segmentation Pipeline...</p>
                    <p className="text-white/60 text-sm mt-2 max-w-md">{analysisProgress}</p>
                  </div>
                )}
                
                {selectedFileObj || mriUrl ? (
                  <NiivueViewer 
                    file={selectedFileObj} 
                    fileName={selectedFile}
                    mriUrl={mriUrl}
                    maskUrl={maskUrl}
                    sliceType={sliceType} 
                    dragMode={dragMode} 
                    azimuth={azimuth}
                    elevation={elevation}
                    className="w-full h-full" 
                  />
                ) : (
                  <div className="text-center">
                    <Brain className="w-20 h-20 text-neutral-700 mx-auto mb-4" />
                    <p className="text-neutral-500 text-lg">{t.brainImage}</p>
                    <p className="text-neutral-600 text-sm mt-2">{t.importToBegin}</p>
                  </div>
                )}
              </div>

              {/* View Settings */}
              <div className="bg-neutral-50 rounded-xl p-6 mb-8 border border-neutral-100 shadow-sm">
                <h3 className="text-lg text-neutral-900 mb-4 font-medium">View Settings</h3>
                <div className="grid grid-cols-2 gap-8">
                  {/* Orientation */}
                  <div>
                    <label className="block text-sm text-neutral-600 mb-2">Orientation</label>
                    <Select.Root value={sliceType} onValueChange={(v) => setSliceType(v as SliceType)}>
                      <Select.Trigger className="w-full bg-white border border-neutral-200 rounded-lg px-3 py-2 flex items-center justify-between text-sm hover:border-neutral-300 transition-colors outline-none focus:ring-2 focus:ring-[#6b7c59]/50">
                        <Select.Value />
                        <ChevronDown className="w-4 h-4 text-neutral-400" />
                      </Select.Trigger>
                      <Select.Portal>
                        <Select.Content position="popper" sideOffset={4} className="z-50 w-full min-w-[200px] bg-white rounded-lg shadow-lg border border-neutral-200 overflow-hidden">
                          <Select.Viewport className="p-1">
                            <Select.Item value="multi" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Multiplanar</Select.ItemText></Select.Item>
                            <Select.Item value="axial" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Axial</Select.ItemText></Select.Item>
                            <Select.Item value="coronal" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Coronal</Select.ItemText></Select.Item>
                            <Select.Item value="sagittal" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Sagittal</Select.ItemText></Select.Item>
                            <Select.Item value="3d" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>3D Render</Select.ItemText></Select.Item>
                          </Select.Viewport>
                        </Select.Content>
                      </Select.Portal>
                    </Select.Root>
                  </div>

                  {/* Mouse Mode */}
                  <div>
                    <label className="block text-sm text-neutral-600 mb-2">Mouse Action</label>
                    <Select.Root value={dragMode} onValueChange={(v) => setDragMode(v as DragMode)}>
                      <Select.Trigger className="w-full bg-white border border-neutral-200 rounded-lg px-3 py-2 flex items-center justify-between text-sm hover:border-neutral-300 transition-colors outline-none focus:ring-2 focus:ring-[#6b7c59]/50">
                        <Select.Value />
                        <ChevronDown className="w-4 h-4 text-neutral-400" />
                      </Select.Trigger>
                      <Select.Portal>
                        <Select.Content position="popper" sideOffset={4} className="z-50 w-full min-w-[200px] bg-white rounded-lg shadow-lg border border-neutral-200 overflow-hidden">
                          <Select.Viewport className="p-1">
                            <Select.Item value="zoom" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Zoom (drag to zoom)</Select.ItemText></Select.Item>
                            <Select.Item value="pan" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Pan (drag to move)</Select.ItemText></Select.Item>
                            <Select.Item value="contrast" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Contrast</Select.ItemText></Select.Item>
                            <Select.Item value="measurement" className="px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-100 cursor-pointer rounded outline-none"><Select.ItemText>Measurement</Select.ItemText></Select.Item>
                          </Select.Viewport>
                        </Select.Content>
                      </Select.Portal>
                    </Select.Root>
                  </div>

                  {/* 3D Angle (Azimuth) */}
                  <div className={sliceType !== '3d' ? 'opacity-50 pointer-events-none' : ''}>
                    <label className="block text-sm text-neutral-600 mb-2 flex justify-between">
                      <span>3D Azimuth</span>
                      <span className="text-neutral-400">{azimuth}°</span>
                    </label>
                    <div className="pt-2">
                      <Slider.Root
                        className="relative flex items-center select-none touch-none w-full h-5"
                        value={[azimuth]}
                        onValueChange={(val: number[]) => setAzimuth(val[0])}
                        max={360}
                        min={0}
                        step={1}
                      >
                        <Slider.Track className="bg-neutral-200 relative grow rounded-full h-1.5">
                          <Slider.Range className="absolute bg-[#6b7c59] rounded-full h-full" />
                        </Slider.Track>
                        <Slider.Thumb
                          className="block w-5 h-5 bg-white shadow-[0_2px_10px] shadow-black/10 rounded-[10px] hover:bg-neutral-50 focus:outline-none focus:ring-2 focus:ring-[#6b7c59]/50"
                          aria-label="3D Azimuth"
                        />
                      </Slider.Root>
                    </div>
                  </div>

                  {/* 3D Angle (Elevation) */}
                  <div className={sliceType !== '3d' ? 'opacity-50 pointer-events-none' : ''}>
                    <label className="block text-sm text-neutral-600 mb-2 flex justify-between">
                      <span>3D Elevation</span>
                      <span className="text-neutral-400">{elevation}°</span>
                    </label>
                    <div className="pt-2">
                      <Slider.Root
                        className="relative flex items-center select-none touch-none w-full h-5"
                        value={[elevation]}
                        onValueChange={(val: number[]) => setElevation(val[0])}
                        max={90}
                        min={-90}
                        step={1}
                      >
                        <Slider.Track className="bg-neutral-200 relative grow rounded-full h-1.5">
                          <Slider.Range className="absolute bg-[#6b7c59] rounded-full h-full" />
                        </Slider.Track>
                        <Slider.Thumb
                          className="block w-5 h-5 bg-white shadow-[0_2px_10px] shadow-black/10 rounded-[10px] hover:bg-neutral-50 focus:outline-none focus:ring-2 focus:ring-[#6b7c59]/50"
                          aria-label="3D Elevation"
                        />
                      </Slider.Root>
                    </div>
                  </div>
                </div>
              </div>

              {/* Analysis Report */}
              <div className="bg-white border border-neutral-200 rounded-xl p-6 shadow-sm">
                <h3 className="text-xl text-neutral-900 mb-5 font-medium">{t.analysisReport}</h3>

                {/* Volume cards */}
                <div className="grid grid-cols-3 gap-4 mb-5">
                  {[
                    { label: t.leftHippocampus,  value: analysisResults?.left_volume,  cls: (analysisResults as any)?.classification_left },
                    { label: t.rightHippocampus, value: analysisResults?.right_volume, cls: (analysisResults as any)?.classification_right },
                    { label: t.totalHippocampus, value: analysisResults?.total_volume, cls: undefined },
                  ].map(({ label, value, cls }) => (
                    <div key={label} className="bg-neutral-50 border border-neutral-100 rounded-xl p-4">
                      <p className="text-xs text-neutral-500 mb-1">{label}</p>
                      <p className="text-xl text-neutral-900 font-semibold">
                        {value !== undefined ? `${value.toLocaleString('fr-FR', { maximumFractionDigits: 0 })} mm³` : '—'}
                      </p>
                      {cls && (
                        <span className={`inline-block mt-1 text-xs font-bold px-2 py-0.5 rounded-full ${
                          cls.toUpperCase() === 'CN'  ? 'bg-green-100 text-green-700' :
                          cls.toUpperCase() === 'MCI' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}>{cls.toUpperCase()}</span>
                      )}
                    </div>
                  ))}
                </div>

                {/* Indicateurs statistiques */}
                {analysisResults && (() => {
                  const ageNum = parseInt(age, 10) || 0;
                  const report = generateClinicalInterpretation(analysisResults as AnalysisData, ageNum);
                  const gradeColor =
                    report.atrophyGrade === 'Normal'  ? 'bg-green-100 text-green-800 border-green-200' :
                    report.atrophyGrade === 'Légère'  ? 'bg-yellow-100 text-yellow-800 border-yellow-200' :
                    report.atrophyGrade === 'Modérée' ? 'bg-orange-100 text-orange-800 border-orange-200' :
                    'bg-red-100 text-red-800 border-red-200';
                  return (
                    <>
                      {/* Badges stats */}
                      <div className="flex gap-3 mb-5 flex-wrap">
                        <div className={`flex-1 min-w-0 rounded-lg border px-3 py-2 text-sm font-medium ${gradeColor}`}>
                          <span className="block text-xs font-normal opacity-70 mb-0.5">Grade d&apos;atrophie</span>
                          Atrophie {report.atrophyGrade}
                        </div>
                        <div className={`flex-1 min-w-0 rounded-lg border px-3 py-2 text-sm font-medium ${
                          report.asymmetrySignificant
                            ? 'bg-red-50 text-red-800 border-red-200'
                            : 'bg-green-50 text-green-800 border-green-200'
                        }`}>
                          <span className="block text-xs font-normal opacity-70 mb-0.5">Asymétrie</span>
                          {report.asymmetryIndex.toFixed(1)} %
                          {report.asymmetrySignificant && ' ⚠ significative'}
                        </div>
                        <div className="flex-1 min-w-0 rounded-lg border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm font-medium text-neutral-700">
                          <span className="block text-xs font-normal text-neutral-500 mb-0.5">Z-score</span>
                          {report.zScore.toFixed(2)}
                          <span className="text-xs text-neutral-400 ml-1">({report.percentOfNorm.toFixed(0)} % norme)</span>
                        </div>
                      </div>

                      {/* Interprétation clinique */}
                      <div className="border-t border-neutral-100 pt-5">
                        <p className="text-sm font-semibold text-neutral-700 mb-3 flex items-center gap-2">
                          <span className="inline-block w-1 h-4 rounded bg-[#6b7c59]" />
                          {t.ageNormalized}
                        </p>
                        <div className="space-y-3">
                          {report.paragraphs.map((para, i) => (
                            <p key={i} className="text-sm text-neutral-700 leading-relaxed">
                              {para}
                            </p>
                          ))}
                        </div>
                      </div>
                    </>
                  );
                })()}

                {/* État vide */}
                {!analysisResults && (
                  <div className="border-t border-neutral-100 pt-4">
                    <p className="text-sm text-neutral-500 italic">{t.ageNormalizedText}</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </Tabs.Content>
      </Tabs.Root>

      {/* Import File Modal */}
      <Dialog.Root open={showImportModal} onOpenChange={setShowImportModal}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed z-50 left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%] bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
            <Dialog.Title className="text-2xl text-neutral-900 mb-3">
              {t.importFileTitle}
            </Dialog.Title>
            <Dialog.Description className="text-neutral-600 mb-6">
              {t.importFileDesc}
            </Dialog.Description>
            <div className="flex gap-3">
              <input 
                type="file" 
                className="hidden" 
                ref={fileInputRef} 
                onChange={handleFileChange}
                accept=".nii,.nii.gz,.dcm"
              />
              <button
                onClick={handleFileSelectClick}
                className="flex-1 bg-[#6b7c59] text-white rounded-xl px-6 py-3 hover:bg-[#5d6b4d] transition-colors"
              >
                {t.selectFile}
              </button>
              <Dialog.Close asChild>
                <button className="flex-1 bg-neutral-100 text-neutral-700 rounded-xl px-6 py-3 hover:bg-neutral-200 transition-colors">
                  {t.cancel}
                </button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Age Modal */}
      <Dialog.Root open={showAgeModal} onOpenChange={setShowAgeModal}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
          <Dialog.Content className="fixed z-50 left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%] bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
            <Dialog.Title className="text-2xl text-neutral-900 mb-3">
              {t.enterAgeTitle}
            </Dialog.Title>
            <Dialog.Description className="text-neutral-600 mb-6">
              {t.enterAgeDesc}
            </Dialog.Description>
            <div className="mb-6">
              <label className="block text-sm text-neutral-700 mb-2">{t.enterAge}</label>
              <input
                type="number"
                min="0"
                value={age}
                onChange={(e) => handleAgeChange(e.target.value)}
                placeholder={t.patientAge}
                className="w-full bg-white border border-neutral-200 rounded-xl px-4 py-3 text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-[#6b7c59]"
                autoFocus
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleAgeConfirm}
                className="flex-1 bg-[#6b7c59] text-white rounded-xl px-6 py-3 hover:bg-[#5d6b4d] transition-colors"
              >
                {t.confirm}
              </button>
              <Dialog.Close asChild>
                <button className="flex-1 bg-neutral-100 text-neutral-700 rounded-xl px-6 py-3 hover:bg-neutral-200 transition-colors">
                  {t.cancel}
                </button>
              </Dialog.Close>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
