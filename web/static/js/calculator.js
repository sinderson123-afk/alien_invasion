let calcFormulaStr = "";
let isNewCalculation = false;

export function initCalculator() {
  const calcFormulaEl = document.getElementById("calc-formula");
  const calcResultEl = document.getElementById("calc-result");
  const calcButtons = document.querySelectorAll(".calc-btn");

  function evaluateCalc() {
    if (!calcFormulaStr) return;

    let jsStr = calcFormulaStr
      .replace(/×/g, "*")
      .replace(/÷/g, "/")
      .replace(/sin\(/g, "Math.sin(")
      .replace(/cos\(/g, "Math.cos(")
      .replace(/tan\(/g, "Math.tan(")
      .replace(/log\(/g, "Math.log10(")
      .replace(/ln\(/g, "Math.log(")
      .replace(/sqrt\(/g, "Math.sqrt(")
      .replace(/\^/g, "**")
      .replace(/π/g, "Math.PI")
      .replace(/e/g, "Math.E");

    const cleaned = jsStr
      .replace(/Math\.(sin|cos|tan|log|log10|sqrt|PI|E)/g, "")
      .replace(/[0-9.+\-*\/()\s\*\*]/g, "");

    if (cleaned.length === 0) {
      try {
        let result = new Function(`return (${jsStr})`)();
        if (typeof result === "number") {
          if (isNaN(result) || !isFinite(result)) {
            calcResultEl.innerText = "Error";
          } else {
            calcResultEl.innerText = Number(result.toFixed(8)).toString();
          }
        } else {
          calcResultEl.innerText = "Error";
        }
      } catch (err) {
        calcResultEl.innerText = "Error";
      }
    } else {
      calcResultEl.innerText = "Error";
    }
    isNewCalculation = true;
  }

  function simulateCalcClick(val) {
    const btn = Array.from(calcButtons).find(b => b.getAttribute("data-val") === val);
    if (btn) btn.click();
  }

  calcButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const val = btn.getAttribute("data-val");

      if (val === "C") {
        calcFormulaStr = "";
        calcFormulaEl.innerText = "";
        calcResultEl.innerText = "0";
        isNewCalculation = false;
      } else if (val === "⌫") {
        if (calcFormulaStr.endsWith("sin(") || calcFormulaStr.endsWith("cos(") || calcFormulaStr.endsWith("tan(") || calcFormulaStr.endsWith("log(") || calcFormulaStr.endsWith("sqrt(")) {
          calcFormulaStr = calcFormulaStr.slice(0, -4);
        } else if (calcFormulaStr.endsWith("ln(")) {
          calcFormulaStr = calcFormulaStr.slice(0, -3);
        } else {
          calcFormulaStr = calcFormulaStr.slice(0, -1);
        }
        calcFormulaEl.innerText = calcFormulaStr;
        isNewCalculation = false;
      } else if (val === "=") {
        evaluateCalc();
      } else {
        if (isNewCalculation) {
          if (["+", "-", "*", "/", "^"].includes(val)) {
            calcFormulaStr = calcResultEl.innerText;
          } else {
            calcFormulaStr = "";
          }
          isNewCalculation = false;
        }

        if (["sin", "cos", "tan", "log", "ln", "sqrt"].includes(val)) {
          calcFormulaStr += val + "(";
        } else if (val === "*") {
          calcFormulaStr += "×";
        } else if (val === "/") {
          calcFormulaStr += "÷";
        } else {
          calcFormulaStr += val;
        }
        calcFormulaEl.innerText = calcFormulaStr;
      }
    });
  });

  window.addEventListener("keydown", (e) => {
    const activeEl = document.activeElement;
    if (activeEl === document.getElementById("memo-textarea") || activeEl === document.getElementById("city-input")) {
      return;
    }

    const key = e.key;
    if (key >= "0" && key <= "9" || ["+", "-", "(", ")", "."].includes(key)) {
      e.preventDefault();
      simulateCalcClick(key);
    } else if (key === "*") {
      e.preventDefault();
      simulateCalcClick("*");
    } else if (key === "/") {
      e.preventDefault();
      simulateCalcClick("/");
    } else if (key === "Enter" || key === "=") {
      e.preventDefault();
      simulateCalcClick("=");
    } else if (key === "Backspace") {
      e.preventDefault();
      simulateCalcClick("⌫");
    } else if (key === "Escape") {
      e.preventDefault();
      simulateCalcClick("C");
    }
  });
}
