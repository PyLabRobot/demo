function autoFillActivationCode() {
  var activationCodeField = document.getElementById("activation_code");

  const params = new URLSearchParams(window.location.search);
  const activationCode = params.get("activation_code");
  if (activationCode) {
    activationCodeField.value = activationCode;
  }
}

window.onload = autoFillActivationCode();

console.log("ok");
