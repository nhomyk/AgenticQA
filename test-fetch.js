async function test() {
  const resp = await fetch("http://localhost:3000/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: "http://localhost:3000" })
  });
  const data = await resp.json();
  console.log("=== RESPONSE KEYS ===");
  console.log(Object.keys(data));
  console.log("\n=== RECOMMENDATIONS ===");
  console.log(JSON.stringify(data.recommendations, null, 2));
}
test().catch(console.error);
