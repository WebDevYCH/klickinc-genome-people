(function (window, document) {
  const variable = '--full-viewport';
  function vh() {
    document.documentElement.style.setProperty(variable, `${window.innerHeight}px`);
  }
  vh();
  window.addEventListener('resize', vh);
  window.addEventListener('orientationchange', vh);
})(window, document);
