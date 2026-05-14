export function optionalElement<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

export function requiredElement<T extends HTMLElement = HTMLElement>(id: string): T {
  const element = optionalElement<T>(id);
  if (!element) {
    throw new Error(`Missing required dashboard element: #${id}`);
  }
  return element;
}

export function optionalQuery<T extends Element = Element>(
  selector: string,
  root: ParentNode = document,
): T | null {
  return root.querySelector<T>(selector);
}

export function queryAll<T extends Element = Element>(
  selector: string,
  root: ParentNode = document,
): NodeListOf<T> {
  return root.querySelectorAll<T>(selector);
}

export function setText(id: string, value: string | number): void {
  const element = optionalElement(id);
  if (element) element.textContent = String(value);
}

export function setHtml(id: string, html: string): void {
  const element = optionalElement(id);
  if (element) element.innerHTML = html;
}

export function datasetValue(element: HTMLElement, key: string): string | null {
  const value = element.dataset[key];
  return value === undefined || value === "" ? null : value;
}
