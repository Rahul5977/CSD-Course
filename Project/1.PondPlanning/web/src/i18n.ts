// Minimal bilingual labels (English / Hindi). Proof of capability for the
// Panchayat-facing screens; the full translation is future work.
export type Lang = "en" | "hi";
const STRINGS: Record<string, [string, string]> = {
  title: ["Village Pond Planner", "ग्राम तालाब योजना"],
  tagline: ["terrain · catchment · runoff · storage — derived from your contour map", "भू-भाग · जलग्रहण · अपवाह · भंडारण — आपके समोच्च मानचित्र से"],
  contourMap: ["Contour map", "समोच्च मानचित्र"],
  village: ["Village", "गाँव"],
  catchment: ["Catchment", "जलग्रहण क्षेत्र"],
  rainfall: ["Rainfall", "वर्षा"],
  pondDesign: ["Pond design", "तालाब डिज़ाइन"],
  land: ["Available land & suitability", "उपलब्ध भूमि और उपयुक्तता"],
  sites: ["Suggested pond sites", "सुझाए गए तालाब स्थल"],
  layers: ["Layers", "परतें"],
  results: ["Results overlay", "परिणाम सारांश"],
  analyse: ["Analyse", "विश्लेषण करें"],
  design: ["Design a pond at the outlet", "निकास पर तालाब डिज़ाइन करें"],
  assess: ["Assess land & rank sites", "भूमि आँकें और स्थल क्रमबद्ध करें"],
  offline: ["Offline — showing the last saved results", "ऑफ़लाइन — अंतिम सहेजे गए परिणाम दिखाए जा रहे हैं"],
};
export function t(key: string, lang: Lang): string {
  const pair = STRINGS[key];
  return pair ? pair[lang === "hi" ? 1 : 0] : key;
}
