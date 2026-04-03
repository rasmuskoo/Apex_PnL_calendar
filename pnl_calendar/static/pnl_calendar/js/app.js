document.addEventListener("htmx:afterSwap", (event) => {
  if (event.target.id === "calendar-block") {
    const monthInput = document.querySelector("#id_month");
    if (monthInput && !monthInput.value) {
      monthInput.valueAsDate = new Date();
    }
  }
});
