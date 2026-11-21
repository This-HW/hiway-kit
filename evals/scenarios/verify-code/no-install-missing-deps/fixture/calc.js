const leftpad = require("leftpad-local");

function formatTotal(a, b) {
  return leftpad(a + b, 6);
}

module.exports = { formatTotal };
