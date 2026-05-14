export function optionalElement(id) {
    return document.getElementById(id);
}
export function requiredElement(id) {
    const element = optionalElement(id);
    if (!element) {
        throw new Error(`Missing required dashboard element: #${id}`);
    }
    return element;
}
export function optionalQuery(selector, root = document) {
    return root.querySelector(selector);
}
export function queryAll(selector, root = document) {
    return root.querySelectorAll(selector);
}
export function setText(id, value) {
    const element = optionalElement(id);
    if (element)
        element.textContent = String(value);
}
export function setHtml(id, html) {
    const element = optionalElement(id);
    if (element)
        element.innerHTML = html;
}
export function datasetValue(element, key) {
    const value = element.dataset[key];
    return value === undefined || value === "" ? null : value;
}
