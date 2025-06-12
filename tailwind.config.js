/** @type {import('tailwindcss').Config} */
const forms = require('@tailwindcss/forms');

module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],

  theme: {
    extend: {},
  },

  plugins: [
    forms,
  ],
};