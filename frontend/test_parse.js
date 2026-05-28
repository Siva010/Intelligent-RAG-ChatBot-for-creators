/**
 * SSE Parse Scratch — RESOLVED
 *
 * This file was a manual test for SSE event parsing behaviour.
 * The underlying bug (break on [DONE] only exiting the inner loop, not the outer
 * while(true) reader loop) has been fixed in:
 *
 *   frontend/src/app/page.tsx — handleSendMessage()
 *
 * Fix: replaced `while(true)` with `let isDone = false; while(!isDone)` and
 * propagated the isDone flag from the inner for-loop break up to the outer loop.
 *
 * This file can be safely deleted. It is kept for reference only.
 */

// Original repro:
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
