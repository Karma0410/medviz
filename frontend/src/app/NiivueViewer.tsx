import { useEffect, useRef } from 'react';
import { Niivue, SLICE_TYPE } from '@niivue/niivue';

export type SliceType = 'multi' | 'axial' | 'coronal' | 'sagittal' | '3d';
export type DragMode = 'contrast' | 'measurement' | 'pan' | 'zoom' | 'none';

interface NiivueViewerProps {
  file?: File | null;
  fileName?: string | null;
  mriUrl?: string | null;
  maskUrl?: string | null;
  className?: string;
  sliceType?: SliceType;
  dragMode?: DragMode;
  azimuth?: number;
  elevation?: number;
}

export default function NiivueViewer({ 
  file,
  fileName,
  mriUrl,
  maskUrl,
  className, 
  sliceType = 'multi', 
  dragMode = 'contrast',
  azimuth = 110,
  elevation = 15
}: NiivueViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nvRef = useRef<any>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    
    // Initialize NiiVue only once
    if (!nvRef.current) {
      const nv = new Niivue({
        show3Dcrosshair: true,
        backColor: [0, 0, 0, 1],
      });
      nv.attachToCanvas(canvasRef.current);
      nvRef.current = nv;
    }
  }, []);

  useEffect(() => {
    if (!nvRef.current) return;
    if (!file && !mriUrl) {
      nvRef.current.clearVolumes();
      return;
    }

    const loadVolumeData = async () => {
      try {
        const volumesToLoad = [];
        let primaryUrl = "";

        if (mriUrl) {
          primaryUrl = mriUrl;
        } else if (file) {
          primaryUrl = URL.createObjectURL(file);
        }

        if (primaryUrl) {
          const fallbackName = fileName ? fileName : 'volume.nii.gz';
          volumesToLoad.push({ 
            url: primaryUrl,
            name: file ? file.name : fallbackName
          });
        }

        if (maskUrl) {
          volumesToLoad.push({
            url: maskUrl,
            name: 'mask.nii.gz',
            colormap: 'red',
            opacity: 0.65,
            cal_min: 0.5,
            cal_max: 2.5
          });
        }

        await nvRef.current.loadVolumes(volumesToLoad);
      } catch (e) {
        console.error("Failed to load volumes in NiiVue", e);
      }
    };

    loadVolumeData();
  }, [file, mriUrl, maskUrl]);

  useEffect(() => {
    if (!nvRef.current) return;
    
    let type = SLICE_TYPE.MULTIPLANAR;
    if (sliceType === 'axial') type = SLICE_TYPE.AXIAL;
    if (sliceType === 'coronal') type = SLICE_TYPE.CORONAL;
    if (sliceType === 'sagittal') type = SLICE_TYPE.SAGITTAL;
    if (sliceType === '3d') type = SLICE_TYPE.RENDER;
    
    nvRef.current.setSliceType(type);
  }, [sliceType]);

  useEffect(() => {
    if (!nvRef.current) return;
    
    switch (dragMode) {
      case 'contrast': nvRef.current.opts.dragMode = nvRef.current.dragModes.contrast; break;
      case 'measurement': nvRef.current.opts.dragMode = nvRef.current.dragModes.measurement; break;
      case 'pan': nvRef.current.opts.dragMode = nvRef.current.dragModes.pan; break;
      case 'zoom': nvRef.current.opts.dragMode = nvRef.current.dragModes.zoom; break;
      case 'none': nvRef.current.opts.dragMode = nvRef.current.dragModes.none; break;
    }
  }, [dragMode]);

  useEffect(() => {
    if (!nvRef.current) return;
    if (typeof nvRef.current.setRenderAzimuthElevation === 'function') {
      nvRef.current.setRenderAzimuthElevation(azimuth, elevation);
    }
  }, [azimuth, elevation]);

  return (
    <div className={`relative ${className}`}>
      <canvas ref={canvasRef} className="absolute top-0 left-0 w-full h-full rounded-2xl outline-none" />
    </div>
  );
}
