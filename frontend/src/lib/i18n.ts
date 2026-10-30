import { useSyncExternalStore } from "react";

export type Lang = "en" | "mr" | "el";

/*
 * English is the reference language. Marathi and Greek are intentionally flagged as
 * draft translations until fluent speakers review them. The selector is shared by
 * the whole application, not stored only inside the Citizen view.
 */
const STR = {
  en: {
    title: "What is planned near me?",
    lede: "Tap anywhere on the map. You will see what is around that spot and whether a new park or mini-forest is proposed there.",
    review: "The Marathi and Greek text on this page are drafts and have not yet been reviewed by fluent speakers. Please treat the English as the reference.",
    example: "Outlined hexagons are sites from an example plan (balanced priorities, a mid-sized budget). Nothing has been decided or built.",
    pick: "Tap the map to choose a place.",
    trees: "Trees counted here: about {n} per hectare (city average: {avg}).",
    noTrees: "No tree count is available for this spot.",
    heat: "On a hot, dry morning the ground here is hotter than {p}% of the city.",
    noHeat: "No ground-temperature reading is available for this spot.",
    parkYes: "About {p}% of people here live within {dist} metres of a mapped public green space of at least {area} hectares.",
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
    trees: "येथे मोजलेली झाडे: सुमारे {n} प्रति हेक्टर (शहराची सरासरी: {avg}).",
    noTrees: "या ठिकाणासाठी झाडांची मोजणी उपलब्ध नाही.",
    heat: "उष्ण, कोरड्या सकाळी येथील जमीन शहराच्या {p}% भागापेक्षा जास्त तापलेली असते.",
    noHeat: "या ठिकाणासाठी जमिनीच्या तापमानाची नोंद उपलब्ध नाही.",
    parkYes: "येथील सुमारे {p}% लोक नकाशावर नोंदलेल्या, किमान {area} हेक्टर आकाराच्या सार्वजनिक हिरवळीपासून {dist} मीटरच्या आत राहतात.",
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
  },
  el: {
    title: "Τι σχεδιάζεται κοντά μου;",
    lede: "Επιλέξτε ένα σημείο στον χάρτη για να δείτε τι υπάρχει εκεί και αν προτείνεται νέο πάρκο ή μικρό αστικό δάσος.",
    review: "Το ελληνικό κείμενο αυτής της σελίδας δεν έχει ελεγχθεί από φυσικό ομιλητή. Χρησιμοποιήστε το αγγλικό κείμενο ως αναφορά.",
    example: "Τα περιγραμμένα εξάγωνα δείχνουν θέσεις ενός ενδεικτικού σχεδίου. Δεν έχει ληφθεί απόφαση και δεν έχει κατασκευαστεί τίποτα.",
    pick: "Επιλέξτε ένα σημείο στον χάρτη.",
    trees: "Καταγεγραμμένα δέντρα εδώ: περίπου {n} ανά εκτάριο (μέσος όρος πόλης: {avg}).",
    noTrees: "Δεν υπάρχει διαθέσιμη καταμέτρηση δέντρων για αυτό το σημείο.",
    heat: "Σε ένα ζεστό, ξηρό πρωινό, το έδαφος εδώ είναι θερμότερο από το {p}% της πόλης.",
    noHeat: "Δεν υπάρχει διαθέσιμη μέτρηση θερμοκρασίας εδάφους για αυτό το σημείο.",
    parkYes: "Περίπου το {p}% των κατοίκων εδώ ζει σε απόσταση {dist} μέτρων από χαρτογραφημένο δημόσιο πράσινο τουλάχιστον {area} εκταρίων.",
    noPark: "Δεν υπάρχουν διαθέσιμα στοιχεία πρόσβασης σε πάρκα για αυτό το σημείο.",
    planYes: "Στο ενδεικτικό σχέδιο προτείνεται εδώ {type}.",
    planNoOpen: "Δεν εντοπίστηκε κατάλληλη ελεύθερη γη εδώ, επομένως δεν προτείνεται θέση.",
    planNo: "Υπάρχει ελεύθερη γη, αλλά άλλες περιοχές έχουν υψηλότερη βαθμολογία ανάγκης στο ενδεικτικό σχέδιο.",
    planUnknown: "Το ενδεικτικό σχέδιο δεν είναι ακόμη διαθέσιμο.",
    pocket_park: "μικρό δημόσιο πάρκο",
    mini_forest: "πυκνό μικρό αστικό δάσος",
    feedbackTitle: "Πείτε μας τη γνώμη σας",
    feedbackLink: "Στείλτε σχόλια",
    feedbackMissing: "Δεν έχει οριστεί ακόμη σύνδεσμος σχολίων για αυτή την εγκατάσταση.",
    simulated: "Πρόκειται για προσομοιώσεις από ανοικτά δεδομένα. Μόνο η αρμόδια τοπική αρχή αποφασίζει τι θα κατασκευαστεί.",
    more: "Δείτε πώς υπολογίζονται οι αριθμοί"
  }
} as const;

const UI = {
  en: {
    nav_atlas: "Atlas", nav_forecast: "Forecast", nav_priority: "Priority", nav_plan: "Plan", nav_compare: "Compare",
    nav_more: "More", nav_citizen: "Citizen view", nav_explore: "Explore", nav_audit: "Data audit",
    nav_evaluation: "Evaluation", nav_method: "Method", nav_language: "Language", nav_city: "City",
    nav_menu: "Menu", nav_light: "Light", nav_dark: "Dark", footer_description: "An evidence base for urban greening decisions.",
    footer_selected: "Selected city", footer_choose: "Choose a city", footer_evidence: "Each city is served from its own data build, and every number carries an evidence label.",
    footer_last_built: "Data last built", footer_credits: "Data and map credits", footer_explore: "Explore",
    footer_best_plan: "Best plan under a budget", footer_need: "Where is the need?", footer_citizen: "Citizen view",
    footer_forecast: "Where the city is heading", footer_map: "Open the map", footer_audit: "See the data audit",
    footer_method: "Read the method and limits",
    translation_notice: "Translation draft: Marathi and Greek interface text has not been reviewed by fluent speakers. Some analytical explanations, chart labels and source details remain in English. English is the reference version."
  },
  mr: {
    nav_atlas: "शहराचा आढावा", nav_forecast: "अंदाज", nav_priority: "प्राधान्य", nav_plan: "आराखडा", nav_compare: "तुलना",
    nav_more: "अधिक", nav_citizen: "नागरिक दृश्य", nav_explore: "अन्वेषण", nav_audit: "माहिती तपासणी",
    nav_evaluation: "मूल्यमापन", nav_method: "पद्धत", nav_language: "भाषा", nav_city: "शहर",
    nav_menu: "मेनू", nav_light: "फिकट थीम", nav_dark: "गडद थीम", footer_description: "शहरी हरितीकरणाच्या निर्णयांसाठी पुराव्यांवर आधारित माहिती.",
    footer_selected: "निवडलेले शहर", footer_choose: "शहर निवडा", footer_evidence: "प्रत्येक शहरासाठी स्वतंत्र माहिती संच वापरला जातो आणि प्रत्येक आकड्याला पुराव्याचे लेबल असते.",
    footer_last_built: "माहितीची शेवटची निर्मिती", footer_credits: "माहिती आणि नकाशाचे स्रोत", footer_explore: "पुढे पाहा",
    footer_best_plan: "अंदाजपत्रकातील सर्वोत्तम आराखडा", footer_need: "गरज कुठे आहे?", footer_citizen: "नागरिक दृश्य",
    footer_forecast: "शहराची पुढील दिशा", footer_map: "नकाशा उघडा", footer_audit: "माहिती तपासणी पहा",
    footer_method: "पद्धत आणि मर्यादा वाचा",
    translation_notice: "भाषांतराचा मसुदा: मराठी आणि ग्रीक इंटरफेस मजकूर अजून जाणकार भाषिकांनी तपासलेला नाही. काही विश्लेषणात्मक स्पष्टीकरणे, आलेखांची लेबले आणि स्रोतांची माहिती इंग्रजीतच आहे. इंग्रजी आवृत्ती प्रमाण मानावी."
  },
  el: {
    nav_atlas: "Επισκόπηση", nav_forecast: "Πρόβλεψη", nav_priority: "Προτεραιότητα", nav_plan: "Σχέδιο", nav_compare: "Σύγκριση",
    nav_more: "Περισσότερα", nav_citizen: "Πολίτες", nav_explore: "Εξερεύνηση", nav_audit: "Έλεγχος δεδομένων",
    nav_evaluation: "Αξιολόγηση", nav_method: "Μεθοδολογία", nav_language: "Γλώσσα", nav_city: "Πόλη",
    nav_menu: "Μενού", nav_light: "Φωτεινό", nav_dark: "Σκοτεινό", footer_description: "Τεκμηρίωση για αποφάσεις αστικού πρασίνου.",
    footer_selected: "Επιλεγμένη πόλη", footer_choose: "Επιλέξτε πόλη", footer_evidence: "Κάθε πόλη χρησιμοποιεί το δικό της σύνολο δεδομένων και κάθε αριθμός συνοδεύεται από ένδειξη τεκμηρίωσης.",
    footer_last_built: "Τελευταία δημιουργία δεδομένων", footer_credits: "Πηγές δεδομένων και χάρτη", footer_explore: "Εξερεύνηση",
    footer_best_plan: "Βέλτιστο σχέδιο εντός προϋπολογισμού", footer_need: "Πού υπάρχει ανάγκη;", footer_citizen: "Πολίτες",
    footer_forecast: "Η μελλοντική πορεία της πόλης", footer_map: "Άνοιγμα χάρτη", footer_audit: "Έλεγχος δεδομένων",
    footer_method: "Μεθοδολογία και περιορισμοί",
    translation_notice: "Πρόχειρη μετάφραση: το κείμενο διεπαφής στα Μαραθικά και τα Ελληνικά δεν έχει ελεγχθεί από φυσικούς ομιλητές. Ορισμένες αναλυτικές εξηγήσεις, ετικέτες γραφημάτων και λεπτομέρειες πηγών παραμένουν στα Αγγλικά. Η αγγλική έκδοση είναι η αναφορά."
  }
} as const;

export type Key = keyof (typeof STR)["en"] | keyof (typeof UI)["en"];
export function t(lang: Lang, key: Key, vars: Record<string, string | number> = {}): string {
  const citizen = STR[lang] as Partial<Record<Key, string>>;
  const ui = UI[lang] as Partial<Record<Key, string>>;
  const englishCitizen = STR.en as Partial<Record<Key, string>>;
  const englishUi = UI.en as Partial<Record<Key, string>>;
  const value = citizen[key] ?? ui[key] ?? englishCitizen[key] ?? englishUi[key] ?? String(key);
  return value.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}

export const LANG_NAME: Record<Lang, string> = { en: "English", mr: "मराठी", el: "Ελληνικά" };

const PAGE_TEXT: Record<Exclude<Lang, "en">, Record<string, string>> = {
  mr: {
    "01 · Trees": "01 · झाडे", "The trees we can actually count.": "आपण प्रत्यक्ष मोजू शकतो अशी झाडे.",
    "02 · Heat": "02 · उष्णता", "Where the ground runs hottest.": "जमीन सर्वाधिक कुठे तापते.",
    "03 · Parks": "03 · उद्याने", "Who can walk to a park.": "उद्यानापर्यंत कोण चालत जाऊ शकते.",
    "04 · Overlap": "04 · एकत्रित परिणाम", "Where heat meets no green.": "जिथे उष्णता आणि हिरवळीचा अभाव एकत्र येतात.",
    "05 · Next": "05 · पुढे", "From a baseline to a decision.": "मूलभूत माहितीकडून निर्णयापर्यंत.",
    "How we stay honest": "आम्ही पारदर्शकता कशी राखतो", "Every number wears a label.": "प्रत्येक आकड्यासोबत पुराव्याचे लेबल आहे.",
    "Built on open data": "मुक्त माहितीवर आधारित", "No paid data. No placeholders.": "सशुल्क माहिती नाही. बनावट माहिती नाही.",
    "Where is the need?": "गरज कुठे आहे?", "Candidate sites": "संभाव्य ठिकाणे",
    "Best portfolio under a budget": "अंदाजपत्रकातील सर्वोत्तम आराखडा", "Layer": "माहितीचा स्तर",
    "Method and limits": "पद्धत आणि मर्यादा",
    "How the baseline is made, and what it cannot tell you.": "मूलभूत माहिती कशी तयार होते आणि ती काय सांगू शकत नाही.",
    "Milestone M8 · Evaluation": "टप्पा M8 · मूल्यमापन",
    "Proof, limits, and what we cannot claim.": "पुरावे, मर्यादा आणि आपण काय दावा करू शकत नाही.",
    "Milestone M5 · Screen 2": "टप्पा M5 · स्क्रीन 2",
    "Where the city is heading.": "शहराची पुढील दिशा.",
    "Milestone M7 · Screen 5": "टप्पा M7 · स्क्रीन 5",
    "Compare plans, against doing nothing.": "काहीही न करण्याच्या पर्यायाशी आराखड्यांची तुलना.",
    "Milestone M0 and M2 · Evidence": "टप्पा M0 आणि M2 · पुरावे",
    "The data audit.": "माहितीची तपासणी."
  },
  el: {
    "01 · Trees": "01 · Δέντρα", "The trees we can actually count.": "Τα δέντρα που μπορούμε πράγματι να μετρήσουμε.",
    "02 · Heat": "02 · Θερμότητα", "Where the ground runs hottest.": "Πού θερμαίνεται περισσότερο το έδαφος.",
    "03 · Parks": "03 · Πάρκα", "Who can walk to a park.": "Ποιοι μπορούν να περπατήσουν μέχρι ένα πάρκο.",
    "04 · Overlap": "04 · Επικάλυψη", "Where heat meets no green.": "Πού η ζέστη συναντά την έλλειψη πρασίνου.",
    "05 · Next": "05 · Επόμενο", "From a baseline to a decision.": "Από τη βασική αποτύπωση στην απόφαση.",
    "How we stay honest": "Πώς διατηρούμε τη διαφάνεια", "Every number wears a label.": "Κάθε αριθμός έχει ένδειξη τεκμηρίωσης.",
    "Built on open data": "Με βάση ανοικτά δεδομένα", "No paid data. No placeholders.": "Χωρίς πληρωμένα δεδομένα. Χωρίς εικονικά στοιχεία.",
    "Where is the need?": "Πού υπάρχει ανάγκη;", "Candidate sites": "Υποψήφιες τοποθεσίες",
    "Best portfolio under a budget": "Βέλτιστο χαρτοφυλάκιο εντός προϋπολογισμού", "Layer": "Επίπεδο",
    "Method and limits": "Μεθοδολογία και περιορισμοί",
    "How the baseline is made, and what it cannot tell you.": "Πώς δημιουργείται η βάση δεδομένων και τι δεν μπορεί να σας πει.",
    "Milestone M8 · Evaluation": "Ορόσημο M8 · Αξιολόγηση",
    "Proof, limits, and what we cannot claim.": "Τεκμήρια, περιορισμοί και όσα δεν μπορούμε να ισχυριστούμε.",
    "Milestone M5 · Screen 2": "Ορόσημο M5 · Οθόνη 2",
    "Where the city is heading.": "Προς τα πού κατευθύνεται η πόλη.",
    "Milestone M7 · Screen 5": "Ορόσημο M7 · Οθόνη 5",
    "Compare plans, against doing nothing.": "Σύγκριση σχεδίων με την επιλογή να μην γίνει τίποτα.",
    "Milestone M0 and M2 · Evidence": "Ορόσημο M0 και M2 · Τεκμηρίωση",
    "The data audit.": "Έλεγχος δεδομένων."
  }
};

export function translatePageText(lang: Lang, text: string): string {
  if (lang === "en") return text;
  return PAGE_TEXT[lang][text] ?? text;
}

function readSavedLanguage(): Lang {
  try {
    const saved = localStorage.getItem("ecometrix-lang");
    return saved === "mr" || saved === "el" ? saved : "en";
  } catch {
    return "en";
  }
}

let activeLanguage: Lang = readSavedLanguage();
const listeners = new Set<() => void>();
function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
function getLanguage() { return activeLanguage; }

export function setLanguage(language: Lang) {
  if (activeLanguage === language) return;
  activeLanguage = language;
  try { localStorage.setItem("ecometrix-lang", language); } catch { /* storage can be disabled */ }
  if (typeof document !== "undefined") document.documentElement.lang = language;
  listeners.forEach(listener => listener());
}

export function useLanguage(): readonly [Lang, typeof setLanguage] {
  const language = useSyncExternalStore(subscribe, getLanguage, (): Lang => "en");
  return [language, setLanguage] as const;
}
