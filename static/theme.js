/**
 * THEME.JS - Toggle Dark/Light Mode + localStorage
 * RPA Logística - VALGROUP
 */

function toggleTheme() {
    var html = document.documentElement;
    var current = html.getAttribute('data-theme') || 'light';
    var next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next);
    localStorage.setItem('rpa-theme', next);
}

// Initial theme application (also called inline in <head> for FOUC prevention)
(function () {
    var theme = localStorage.getItem('rpa-theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
})();
