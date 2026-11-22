/** Natywne pole `type="date"`: kalendarz przeglądarki otwiera się po kliknięciu w całe pole, nie tylko w ikonę. */
export function openNativePicker(el: HTMLInputElement) {
  try {
    el.showPicker?.()
  } catch {
    // starsze przeglądarki albo brak gestu użytkownika — zostaje zwykłe pole
  }
}
