const text = `data: {"chunk": "winner.\\n\\nHere "}\n\n`;
const lines = text.split('\n');
for (const line of lines) {
  if (line.startsWith('data: ')) {
    const dataStr = line.slice(6).trim();
    try {
      console.log("Parsed:", JSON.parse(dataStr));
    } catch (e) {
      console.log("Error:", e.message);
    }
  }
}
