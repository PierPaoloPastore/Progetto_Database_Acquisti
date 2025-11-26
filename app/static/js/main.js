// JS principale minimale.
// - gestione auto-hide dei flash messages
// - piccoli helper globali

document.addEventListener("DOMContentLoaded", () => {
  const flashContainer = document.getElementById("flash-container");
  if (flashContainer) {
    setTimeout(() => {
      flashContainer.style.opacity = "0";
      setTimeout(() => {
        if (flashContainer.parentNode) {
          flashContainer.parentNode.removeChild(flashContainer);
        }
      }, 400);
    }, 4000);
  }
});
