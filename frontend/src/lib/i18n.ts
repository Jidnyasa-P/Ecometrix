export type Lang = "en" | "mr";

/* The Marathi strings are NOT yet reviewed by a fluent speaker. The citizen page says so, in both languages,
   and the English text is the reference. Replace or confirm these before any public launch. */
const STR = {
  en: {
    title: "What is planned near me?",
    lede: "Tap anywhere on the map. You will see what is around that spot and whether a new park or mini-forest is proposed there.",
    review: "The Marathi text on this page has not yet been reviewed by a fluent speaker. Please treat the English as the reference.",
    example: "Outlined hexagons are sites from an example plan (balanced priorities, a mid-sized budget). Nothing has been decided or built.",
    pick: "Tap the map to choose a place.",
    trees: "Trees counted here: about {n} per hectare (Pune average: {avg}).",
    noTrees: "No tree count is available for this spot.",
    heat: "On a hot, dry morning the ground here is hotter than {p}% of the city.",
    noHeat: "No ground-temperature reading is available for this spot.",
    parkYes: "About {p}% of people here live within about 300 metres of a mapped park of at least half a hectare.",
    noPark: "No park-access figure is available for this spot.",
    planYes: "In the example plan, a {type} is proposed in this area.",
    planNoOpen: "No suitable open land was found in this area, so no site is proposed.",
    planNo: "Open land exists here, but other areas scored higher for need within the budget of the example plan.",
    planUnknown: "The example plan is not available yet.",
    pocket_park: "pocket park (a small public park)",
    mini_forest: "dense mini-forest",
    feedbackTitle: "Tell us what you think",
    feedbackLink: "Send feedback",
    feedbackMissing: "A feedback link has not been set up for this deployment yet.",
    simulated: "These are simulations from open data. Only the municipality can decide what is built.",
    more: "See how the numbers are made"
  },
  mr: {
    title: "माझ्या जवळ काय नियोजित आहे?",
    lede: "नकाशावर कुठेही स्पर्श करा. त्या ठिकाणी काय आहे आणि तिथे नवीन उद्यान किंवा मिनी-जंगल प्रस्तावित आहे का, ते दिसेल.",
    review: "या पानावरील मराठी मजकूर अजून मराठी भाषेच्या जाणकाराकडून तपासलेला नाही. कृपया इंग्रजी मजकूर प्रमाण मानावा.",
    example: "बाह्यरेषा असलेले षटकोन एका उदाहरण आराखड्यातील ठिकाणे आहेत (संतुलित प्राधान्य, मध्यम अंदाजपत्रक). काहीही ठरलेले किंवा बांधलेले नाही.",
    pick: "ठिकाण निवडण्यासाठी नकाशावर स्पर्श करा.",
    trees: "येथे मोजलेली झाडे: सुमारे {n} प्रति हेक्टर (पुण्याची सरासरी: {avg}).",
    noTrees: "या ठिकाणासाठी झाडांची मोजणी उपलब्ध नाही.",
    heat: "उष्ण, कोरड्या सकाळी येथील जमीन शहराच्या {p}% भागापेक्षा जास्त तापलेली असते.",
    noHeat: "या ठिकाणासाठी जमिनीच्या तापमानाची नोंद उपलब्ध नाही.",
    parkYes: "येथील सुमारे {p}% लोक नकाशावर नोंदलेल्या, किमान अर्धा हेक्टर आकाराच्या उद्यानापासून सुमारे 300 मीटरच्या आत राहतात.",
    noPark: "या ठिकाणासाठी उद्यानाच्या उपलब्धतेची आकडेवारी उपलब्ध नाही.",
    planYes: "उदाहरण आराखड्यात या भागात {type} प्रस्तावित आहे.",
    planNoOpen: "या भागात योग्य मोकळी जमीन आढळली नाही, म्हणून कोणतेही ठिकाण प्रस्तावित नाही.",
    planNo: "येथे मोकळी जमीन आहे, पण उदाहरण आराखड्याच्या अंदाजपत्रकात इतर भागांना गरजेचे जास्त गुण मिळाले.",
    planUnknown: "उदाहरण आराखडा अजून उपलब्ध नाही.",
    pocket_park: "छोटे सार्वजनिक उद्यान",
    mini_forest: "दाट मिनी-जंगल",
    feedbackTitle: "तुमचे मत कळवा",
    feedbackLink: "अभिप्राय पाठवा",
    feedbackMissing: "या तैनातीसाठी अभिप्रायाचा दुवा अजून तयार केलेला नाही.",
    simulated: "हे खुल्या माहितीवर आधारित अंदाज आहेत. काय बांधायचे ते फक्त महानगरपालिका ठरवू शकते.",
    more: "आकडे कसे तयार होतात ते पहा"
  }
} as const;

export type Key = keyof (typeof STR)["en"];
export function t(lang: Lang, key: Key, vars: Record<string, string | number> = {}): string {
  const s: string = (STR[lang]?.[key] ?? STR.en[key]) as string;      // untranslated strings fall back to English
  return s.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}
export const LANG_NAME: Record<Lang, string> = { en: "English", mr: "मराठी" };
