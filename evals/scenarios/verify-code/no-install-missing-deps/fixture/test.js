const assert = require("assert");
const { formatTotal } = require("./calc");

assert.strictEqual(formatTotal(2, 3), "     5");
console.log("ok");
