/** Keep the selected city on in-app navigation without carrying unrelated filters across screens. */
export function cityPath(path: string, search = window.location.search): string {
  const city = new URLSearchParams(search).get("city");
  if (!city) return path;
  const [pathname, query = ""] = path.split("?", 2);
  const params = new URLSearchParams(query);
  params.set("city", city);
  return `${pathname}?${params.toString()}`;
}
