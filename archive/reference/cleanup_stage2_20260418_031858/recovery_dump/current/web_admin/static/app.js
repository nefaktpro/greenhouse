function logout() {
  localStorage.removeItem("gh_token");
  window.location.href = "/web/login";
}
