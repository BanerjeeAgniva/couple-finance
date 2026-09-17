// Category → icon + brand-colour lookup tables. Pure; no DOM, no app state.

// category name -> drawn icon (keyword match, own/open-source-style SVGs in the sprite)
export const CAT_ICONS = [
  // delivery apps first, so the brand name wins over the generic grocery/dining/shopping match
  [["swiggy", "zomato", "food delivery", "eatsure"], "i-cat-delivery"],
  [["blinkit", "zepto", "instamart", "pronto", "dunzo", "quick"], "i-cat-quick"],
  [["amazon", "flipkart", "myntra", "meesho", "parcel", "courier", "delivery"], "i-cat-package"],
  [["snabbit", "urbanclap", "urban company", "service", "salon", "repair", "plumber", "electrician", "handyman"], "i-cat-services"],
  [["furlenco", "rentomojo", "rentmojo"], "i-cat-furniture"],  // before "rent", since these contain it
  [["rent", "mortgage", "lease"], "i-cat-rent"],
  [["grocer", "supermarket", "mart", "bigbasket", "zepto", "blinkit"], "i-cat-groceries"],
  [["eat", "dining", "restaurant", "food", "swiggy", "zomato", "cafe", "dinner", "lunch"], "i-cat-dining"],
  [["util", "electric", "power", "water", "gas", "internet", "wifi", "phone", "broadband", "bill", "trash", "clean"], "i-cat-utilities"],
  [["travel", "flight", "plane", "hotel", "trip", "airbnb", "vacation"], "i-cat-travel"],
  [["transport", "uber", "rapido", "ola", "taxi", "cab", "car", "fuel", "petrol", "diesel", "bus", "train", "metro", "auto", "parking"], "i-cat-transport"],
  [["furnitur", "rental", "ikea", "sofa", "decor", "appliance", "fridge"], "i-cat-furniture"],
  [["shop", "amazon", "flipkart", "cloth", "apparel", "shoe", "slipper"], "i-cat-shopping"],
  [["health", "medic", "doctor", "pharma", "hospital", "medicine", "fitness", "gym"], "i-cat-health"],
  [["movie", "game", "music", "entertain", "netflix", "spotify", "subscription", "ott"], "i-cat-fun"],
  [["gift", "present", "donation"], "i-cat-gift"],
  [["educat", "school", "college", "course", "tuition", "book"], "i-cat-education"],
  [["pet", "dog"], "i-cat-pets"],
];
export function catIconId(name) {
  const n = (name || "").toLowerCase();
  for (const [keys, id] of CAT_ICONS) if (keys.some((k) => n.includes(k))) return id;
  return "i-cat-other";
}

// signature icon tint per delivery/company category (mid-tones legible on light + dark)
export const CAT_COLORS = [
  [["amazon"], "#f59e0b"],
  [["swiggy"], "#f97316"],
  [["zomato"], "#ef4444"],
  [["zepto"], "#8b5cf6"],
  [["blinkit"], "#eab308"],
  [["instamart"], "#ec4899"],
  [["flipkart"], "#2874f0"],
  [["pronto"], "#06b6d4"],
  [["furlenco"], "#6366f1"],
  [["rentomojo", "rentmojo"], "#14b8a6"],
  [["snabbit"], "#22c55e"],
  [["urbanclap"], "#a21caf"],
  [["rapido"], "#facc15"],
  [["uber"], "#64748b"],
];
export function catColor(name) {
  const n = (name || "").toLowerCase();
  for (const [keys, c] of CAT_COLORS) if (keys.some((k) => n.includes(k))) return c;
  return "";
}
export const catColorStyle = (name) => { const c = catColor(name); return c ? ` style="color:${c}"` : ""; };
