import { jsPDF } from 'jspdf';


export interface AnalysisData {
  left_volume: number;           
  right_volume: number;          
  total_volume: number;          
  brain_volume?: number;         
  asymmetry_index?: number;      
  dice_left?: number;            
  dice_right?: number;           
  iou_left?: number;             
  iou_right?: number;            
  classification_left?: string;  
  classification_right?: string;
  status_text?: string;          
}


interface AgeNorm {
  mean: number;
  sd: number;
}

function getAgeNorm(age: number): AgeNorm {
  if (age < 50)  return { mean: 8200, sd: 800 };
  if (age < 60)  return { mean: 7600, sd: 750 };
  if (age < 65)  return { mean: 7000, sd: 700 };
  if (age < 70)  return { mean: 6500, sd: 680 };
  if (age < 75)  return { mean: 6100, sd: 650 };
  if (age < 80)  return { mean: 5700, sd: 620 };
  if (age < 85)  return { mean: 5300, sd: 600 };
  return          { mean: 4900, sd: 580 };
}


type AtrophyGrade = 'Normal' | 'Légère' | 'Modérée' | 'Sévère';

function classifyAtrophy(zScore: number): AtrophyGrade {
  if (zScore > -1.0) return 'Normal';
  if (zScore > -1.5) return 'Légère';
  if (zScore > -2.0) return 'Modérée';
  return 'Sévère';
}


function interpretClassification(cls?: string): string {
  if (!cls) return '';
  const c = cls.toUpperCase();
  if (c === 'CN')  return 'cognition normale (CN)';
  if (c === 'MCI') return 'trouble cognitif léger (MCI — Mild Cognitive Impairment)';
  if (c === 'AD')  return "maladie d'Alzheimer (AD)";
  return cls;
}


interface ClinicalReport {
  atrophyGrade: AtrophyGrade;
  zScore: number;
  percentOfNorm: number;
  asymmetryIndex: number;
  asymmetrySignificant: boolean;
  paragraphs: string[];
}

export function generateClinicalInterpretation(
  data: AnalysisData,
  age: number
): ClinicalReport {
  const { mean, sd } = getAgeNorm(age);
  const totalMm3 = data.total_volume;
  const leftMm3  = data.left_volume;
  const rightMm3 = data.right_volume;

  const zScore = (totalMm3 - mean) / sd;
  const percentOfNorm = (totalMm3 / mean) * 100;
  const grade = classifyAtrophy(zScore);

  const asymmetryIndex =
    data.asymmetry_index !== undefined
      ? data.asymmetry_index
      : leftMm3 + rightMm3 > 0
        ? (Math.abs(leftMm3 - rightMm3) / Math.max(leftMm3, rightMm3)) * 100
        : 0;
  const asymmetrySignificant = asymmetryIndex >= 15;

  const dominantSide =
    leftMm3 < rightMm3 ? 'gauche' : rightMm3 < leftMm3 ? 'droit' : null;

  const paragraphs: string[] = [];

  const normDesc =
    grade === 'Normal'
      ? `dans les limites normales pour un patient de ${age} ans`
      : `inférieur à la norme attendue pour un patient de ${age} ans`;

  paragraphs.push(
    `L'analyse volumétrique de l'hippocampe révèle un volume total de ` +
    `${totalMm3.toLocaleString('en-US', { maximumFractionDigits: 0 }).replaceAll(",", " ")} mm³, ` +
    `${normDesc} ` +
    `(valeur de référence : ${mean.toLocaleString('en-US').replaceAll(",", " ")} ± ${sd.toLocaleString('en-US').replaceAll(",", " ")} mm³, ` +
    `z-score = ${zScore.toFixed(2)}). ` +
    `Ce volume représente ${percentOfNorm.toFixed(1)} % de la moyenne normative ajustée à l'âge.`
  );

  if (grade === 'Normal') {
    paragraphs.push(
      `Le degré d'atrophie hippocampique est classé comme ${grade.toLowerCase()}, ` +
      `ce qui est cohérent avec le vieillissement physiologique attendu. ` +
      `Aucune réduction volumétrique pathologique significative n'est mise en évidence à ce stade.`
    );
  } else {
    const gradeDesc: Record<AtrophyGrade, string> = {
      'Normal':   '',
      'Légère':   'une réduction volumétrique discrète, pouvant précéder une atteinte cliniquement significative',
      'Modérée':  'une réduction volumétrique modérée, compatible avec un stade prodromal ou une démence débutante',
      'Sévère':   'une réduction volumétrique marquée, évocatrice d\'une atteinte neurodégénérative avancée',
    };
    paragraphs.push(
      `L'atrophie hippocampique est qualifiée de grade « ${grade} » (z-score : ${zScore.toFixed(2)}), ` +
      `correspondant à ${gradeDesc[grade]}. ` +
      `Ce niveau d'atrophie dépasse le seuil physiologique attendu pour la tranche d'âge et ` +
      `mérite une corrélation avec les données cliniques et neuropsychologiques.`
    );
  }

  if (asymmetrySignificant && dominantSide) {
    paragraphs.push(
      `Une asymétrie volumétrique significative est observée entre les deux hippocampes ` +
      `(index d'asymétrie : ${asymmetryIndex.toFixed(1)} % ; seuil clinique : 15 %). ` +
      `L'hippocampe ${dominantSide} présente un volume plus faible ` +
      `(gauche : ${leftMm3.toLocaleString('en-US', { maximumFractionDigits: 0 }).replaceAll(",", " ")} mm³, ` +
      `droit : ${rightMm3.toLocaleString('en-US', { maximumFractionDigits: 0 }).replaceAll(",", " ")} mm³). ` +
      `Une telle asymétrie peut orienter vers une atteinte focalisée ou une évolution ` +
      `asymétrique de la pathologie sous-jacente.`
    );
  } else if (asymmetryIndex > 0) {
    paragraphs.push(
      `La répartition volumétrique entre l'hippocampe gauche ` +
      `(${leftMm3.toLocaleString('en-US', { maximumFractionDigits: 0 }).replaceAll(",", " ")} mm³) ` +
      `et droit (${rightMm3.toLocaleString('en-US', { maximumFractionDigits: 0 }).replaceAll(",", " ")} mm³) ` +
      `est relativement symétrique (index d'asymétrie : ${asymmetryIndex.toFixed(1)} %), ` +
      `sans asymétrie significative dépassant le seuil de 15 %.`
    );
  }

  const clsLeft  = interpretClassification(data.classification_left);
  const clsRight = interpretClassification(data.classification_right);

  if (clsLeft || clsRight) {
    if (clsLeft === clsRight && clsLeft) {
      paragraphs.push(
        `La classification automatique par l'algorithme de segmentation indique une présentation ` +
        `bilatérale compatible avec une ${clsLeft}. ` +
        (data.classification_left?.toUpperCase() === 'AD'
          ? `Cette conclusion doit être mise en regard du tableau clinique complet, ` +
            `incluant les tests neuropsychologiques (MMSE, MoCA) et les marqueurs biologiques.`
          : `Ce résultat algorithmique doit être interprété avec précaution et ` +
            `corrélé à l'évaluation clinique globale.`)
      );
    } else if (clsLeft && clsRight) {
      paragraphs.push(
        `La classification automatique suggère une discordance entre les deux hippocampes : ` +
        `hippocampe gauche → ${clsLeft} ; hippocampe droit → ${clsRight}. ` +
        `Cette asymétrie de classification renforce la nécessité d'une évaluation clinique approfondie.`
      );
    }
  }

  if (grade === 'Normal') {
    paragraphs.push(
      `Au vu des résultats, un suivi volumétrique de contrôle dans 12 à 18 mois peut ` +
      `être envisagé dans le cadre d'un protocole de surveillance, en particulier si ` +
      `des symptômes cognitifs sont rapportés par le patient ou son entourage.`
    );
  } else {
    paragraphs.push(
      `Ces résultats justifient une corrélation clinique rigoureuse, incluant : ` +
      `(1) un bilan neuropsychologique standardisé, (2) une analyse des facteurs de risque ` +
      `cardiovasculaires et métaboliques, et (3) si pertinent, des examens complémentaires ` +
      `(TEP-FDG, dosage des biomarqueurs du LCR, biomarqueurs sanguins amyloïdes). ` +
      `Un suivi longitudinal de la volumétrie est recommandé.`
    );
  }

  return {
    atrophyGrade: grade,
    zScore,
    percentOfNorm,
    asymmetryIndex,
    asymmetrySignificant,
    paragraphs,
  };
}


const COLORS = {
  primary:    [107, 124,  89] as [number, number, number], // #6b7c59
  dark:       [ 31,  31,  31] as [number, number, number],
  medium:     [ 90,  90,  90] as [number, number, number],
  light:      [140, 140, 140] as [number, number, number],
  border:     [210, 214, 205] as [number, number, number],
  bgSection:  [245, 247, 242] as [number, number, number],
  bgWarning:  [255, 248, 235] as [number, number, number],
  warning:    [180, 120,  20] as [number, number, number],
  white:      [255, 255, 255] as [number, number, number],
  danger:     [180,  50,  50] as [number, number, number],
  ok:         [ 60, 130,  60] as [number, number, number],
};

function setColor(doc: jsPDF, rgb: [number, number, number]) {
  doc.setTextColor(rgb[0], rgb[1], rgb[2]);
}

function setFill(doc: jsPDF, rgb: [number, number, number]) {
  doc.setFillColor(rgb[0], rgb[1], rgb[2]);
}

function setDraw(doc: jsPDF, rgb: [number, number, number]) {
  doc.setDrawColor(rgb[0], rgb[1], rgb[2]);
}

function wrapText(doc: jsPDF, text: string, maxWidth: number): string[] {
  return doc.splitTextToSize(text, maxWidth);
}

function roundedRect(
  doc: jsPDF,
  x: number, y: number,
  w: number, h: number,
  r: number,
  fill: [number, number, number],
  stroke?: [number, number, number],
) {
  setFill(doc, fill);
  if (stroke) {
    setDraw(doc, stroke);
    doc.roundedRect(x, y, w, h, r, r, 'FD');
  } else {
    doc.roundedRect(x, y, w, h, r, r, 'F');
  }
}

function hLine(doc: jsPDF, x1: number, x2: number, y: number, rgb: [number, number, number]) {
  setDraw(doc, rgb);
  doc.setLineWidth(0.3);
  doc.line(x1, y, x2, y);
}

function drawGradeBadge(doc: jsPDF, grade: AtrophyGrade, x: number, y: number) {
  const colors: Record<AtrophyGrade, [number, number, number]> = {
    Normal:  COLORS.ok,
    Légère:  [200, 150,  30],
    Modérée: [200,  90,  20],
    Sévère:  COLORS.danger,
  };
  const bg: Record<AtrophyGrade, [number, number, number]> = {
    Normal:  [230, 245, 230],
    Légère:  [255, 248, 220],
    Modérée: [255, 235, 220],
    Sévère:  [255, 225, 225],
  };
  const w = 40, h = 7, r = 2;
  roundedRect(doc, x, y - 5, w, h, r, bg[grade], colors[grade]);
  setColor(doc, colors[grade]);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8);
  doc.text(`Atrophie ${grade}`, x + w / 2, y - 0.5, { align: 'center' });
}


export function exportReportAsPDF(
  data: AnalysisData,
  age: number,
  sourceFilename: string,
) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' });

  const PAGE_W  = 210;
  const PAGE_H  = 297;
  const MARGIN  = 18;
  const COL_W   = PAGE_W - MARGIN * 2;

  let y = MARGIN;

  roundedRect(doc, 0, 0, PAGE_W, 38, 0, COLORS.primary);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(20);
  setColor(doc, COLORS.white);
  doc.text('NeuroVolumetry', MARGIN, 16);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  setColor(doc, [220, 228, 210]);
  doc.text('Rapport d\'Analyse Volumétrique Hippocampique', MARGIN, 24);

  const now = new Date();
  const dateStr = now.toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'long', year: 'numeric'
  });
  doc.setFontSize(9);
  setColor(doc, [190, 205, 175]);
  doc.text(dateStr, PAGE_W - MARGIN, 16, { align: 'right' });

  doc.setFontSize(7.5);
  setColor(doc, [190, 205, 175]);
  doc.text('Outil de recherche — Non destiné à un usage clinique autonome', PAGE_W - MARGIN, 24, { align: 'right' });

  y = 48;

  roundedRect(doc, MARGIN, y, COL_W, 22, 3, COLORS.bgSection, COLORS.border);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  setColor(doc, COLORS.primary);
  doc.text('INFORMATIONS PATIENT', MARGIN + 5, y + 7);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  setColor(doc, COLORS.dark);

  const fn = sourceFilename.length > 45
    ? sourceFilename.slice(0, 42) + '...'
    : sourceFilename;

  doc.text(`Âge du patient :  ${age} ans`, MARGIN + 5, y + 14);
  doc.text(`Fichier source :  ${fn}`, MARGIN + 5 + 80, y + 14);

  y += 30;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  setColor(doc, COLORS.dark);
  doc.text('Résultats Volumétriques', MARGIN, y);
  hLine(doc, MARGIN, PAGE_W - MARGIN, y + 2, COLORS.border);
  y += 9;

  const cardW = (COL_W - 8) / 3;
  const cards = [
    { label: 'Hippocampe gauche', value: data.left_volume, cls: data.classification_left },
    { label: 'Hippocampe droit',  value: data.right_volume, cls: data.classification_right },
    { label: 'Volume total hippo.', value: data.total_volume, cls: undefined },
  ];

  cards.forEach((card, i) => {
    const cx = MARGIN + i * (cardW + 4);
    roundedRect(doc, cx, y, cardW, 28, 3, COLORS.bgSection, COLORS.border);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    setColor(doc, COLORS.medium);
    doc.text(card.label, cx + cardW / 2, y + 7, { align: 'center' });

    const volStr = `${card.value.toLocaleString('en-US', { maximumFractionDigits: 0 }).replaceAll(",", " ")} mm³`;
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(14);
    setColor(doc, COLORS.dark);
    doc.text(volStr, cx + cardW / 2, y + 16, { align: 'center' });

    if (card.cls) {
      const clsColor = card.cls.toUpperCase() === 'CN' ? COLORS.ok
        : card.cls.toUpperCase() === 'MCI' ? ([200, 150, 30] as [number, number, number])
        : COLORS.danger;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(8);
      setColor(doc, clsColor);
      doc.text(card.cls.toUpperCase(), cx + cardW / 2, y + 24, { align: 'center' });
    }
  });

  y += 34;

  if (data.brain_volume !== undefined) {
    roundedRect(doc, MARGIN, y, COL_W, 14, 3, COLORS.bgSection, COLORS.border);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    setColor(doc, COLORS.medium);
    doc.text('Volume cérébral total :', MARGIN + 5, y + 6);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9);
    setColor(doc, COLORS.dark);
    doc.text(
      `${data.brain_volume.toLocaleString('en-US', { maximumFractionDigits: 0 }).replaceAll(",", " ")} mm³`,
      MARGIN + 55, y + 6
    );
   
    const ratioLeft  = (data.left_volume  / data.brain_volume * 100).toFixed(2);
    const ratioRight = (data.right_volume / data.brain_volume * 100).toFixed(2);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    setColor(doc, COLORS.medium);
    doc.text(
      `Ratio hippo/cerveau — G : ${ratioLeft} %   D : ${ratioRight} %`,
      MARGIN + 5, y + 11
    );
    y += 20;
  }

  const hasQuality = data.dice_left !== undefined || data.dice_right !== undefined;
  if (hasQuality) {
    roundedRect(doc, MARGIN, y, COL_W, 18, 3, COLORS.bgSection, COLORS.border);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8.5);
    setColor(doc, COLORS.medium);
    doc.text('Métriques de qualité de segmentation', MARGIN + 5, y + 7);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    setColor(doc, COLORS.dark);

    const qMetrics: string[] = [];
    if (data.dice_left  !== undefined) qMetrics.push(`Dice gauche : ${(data.dice_left  * 100).toFixed(1)} %`);
    if (data.dice_right !== undefined) qMetrics.push(`Dice droit : ${(data.dice_right * 100).toFixed(1)} %`);
    if (data.iou_left   !== undefined) qMetrics.push(`IoU gauche : ${(data.iou_left   * 100).toFixed(1)} %`);
    if (data.iou_right  !== undefined) qMetrics.push(`IoU droit : ${(data.iou_right  * 100).toFixed(1)} %`);

    doc.text(qMetrics.join('    ·    '), MARGIN + 5, y + 14);
    y += 24;
  }

  const report = generateClinicalInterpretation(data, age);

  const asymStr = `Index d'asymétrie : ${report.asymmetryIndex.toFixed(1)} %`;
  const asymColor = report.asymmetrySignificant ? COLORS.danger : COLORS.ok;
  const asymBg: [number, number, number] = report.asymmetrySignificant
    ? [255, 225, 225] : [230, 245, 230];
  const asymBorder: [number, number, number] = report.asymmetrySignificant
    ? COLORS.danger : COLORS.ok;

  roundedRect(doc, MARGIN, y, COL_W / 2 - 2, 13, 3, asymBg, asymBorder);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  setColor(doc, asymColor);
  doc.text(asymStr, MARGIN + (COL_W / 2 - 2) / 2, y + 5.5, { align: 'center' });
  if (report.asymmetrySignificant) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.5);
    doc.text('⚠ Asymétrie significative (> 15 %)', MARGIN + (COL_W / 2 - 2) / 2, y + 10, { align: 'center' });
  } else {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.5);
    doc.text('Asymétrie dans les limites acceptables', MARGIN + (COL_W / 2 - 2) / 2, y + 10, { align: 'center' });
  }

  const zStr = `Z-score : ${report.zScore.toFixed(2)}`;
  const normRef = `(réf. : ${getAgeNorm(age).mean.toLocaleString('en-US').replaceAll(",", " ")} ± ${getAgeNorm(age).sd} mm³)`;
  roundedRect(doc, MARGIN + COL_W / 2 + 2, y, COL_W / 2 - 2, 13, 3, COLORS.bgSection, COLORS.border);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  setColor(doc, COLORS.dark);
  doc.text(zStr, MARGIN + COL_W / 2 + 2 + (COL_W / 2 - 2) / 2, y + 5.5, { align: 'center' });
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7.5);
  setColor(doc, COLORS.light);
  doc.text(normRef, MARGIN + COL_W / 2 + 2 + (COL_W / 2 - 2) / 2, y + 10, { align: 'center' });

  y += 19;

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(11);
  setColor(doc, COLORS.dark);
  doc.text('Interprétation Clinique', MARGIN, y);
  hLine(doc, MARGIN, PAGE_W - MARGIN, y + 2, COLORS.border);

  drawGradeBadge(doc, report.atrophyGrade, PAGE_W - MARGIN - 45, y + 2);

  y += 9;
  const interpX = MARGIN + 4;
  const interpW = COL_W - 4;
  const lineH   = 5.2;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9.5);

  let totalInterpH = 0;
  const wrappedParagraphs: string[][] = report.paragraphs.map((p, idx) => {
    const lines = wrapText(doc, p, interpW - 10);
    totalInterpH += lines.length * lineH + (idx < report.paragraphs.length - 1 ? 4 : 0);
    return lines;
  });
  totalInterpH += 8; 

  roundedRect(doc, MARGIN, y, COL_W, totalInterpH, 3, COLORS.bgSection, COLORS.border);
  setFill(doc, COLORS.primary);
  doc.roundedRect(MARGIN, y, 3, totalInterpH, 1.5, 1.5, 'F');

  let ty = y + 6;
  wrappedParagraphs.forEach((lines, idx) => {
    setColor(doc, COLORS.dark);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9.5);
    lines.forEach((line) => {
      doc.text(line, interpX + 6, ty);
      ty += lineH;
    });
    if (idx < wrappedParagraphs.length - 1) ty += 4;
  });

  y += totalInterpH + 8;

  
  const warningH = 22;
  if (y + warningH > PAGE_H - 15) {
    doc.addPage();
    y = MARGIN;
  }

  roundedRect(doc, MARGIN, y, COL_W, warningH, 3, COLORS.bgWarning, [220, 180, 50]);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  setColor(doc, COLORS.warning);
  doc.text('⚠', MARGIN + 5, y + 10);

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(8.5);
  setColor(doc, COLORS.warning);
  doc.text('AVERTISSEMENT IMPORTANT', MARGIN + 13, y + 7);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  setColor(doc, [120, 90, 10]);
  const warningText =
    'Ce rapport est un outil de recherche et de support diagnostique. Il ne remplace ' +
    'en aucun cas l\'avis d\'un professionnel de santé qualifié. Tous les résultats doivent ' +
    'être interprétés par un médecin spécialiste (neurologue, radiologue) en conjonction ' +
    'avec l\'évaluation clinique complète et d\'autres examens diagnostiques.';
  const warningLines = wrapText(doc, warningText, COL_W - 22);
  warningLines.forEach((line, i) => {
    doc.text(line, MARGIN + 13, y + 13 + i * 4);
  });

  y += warningH + 6;

  hLine(doc, MARGIN, PAGE_W - MARGIN, PAGE_H - 12, COLORS.border);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7.5);
  setColor(doc, COLORS.light);
  doc.text('NeuroVolumetry — Analyse Hippocampique Automatisée', MARGIN, PAGE_H - 7);
  doc.text(`Généré le ${dateStr}`, PAGE_W - MARGIN, PAGE_H - 7, { align: 'right' });

  const safeName = sourceFilename.replace(/[^a-zA-Z0-9_-]/g, '_');
  doc.save(`NeuroVolumetry_Report_${age}yo_${safeName}.pdf`);
}
