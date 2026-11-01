// Renders a recipe poster (an HTML file with a `.poster` element) to PNG
// using the Playwright + Chromium that is pre-installed in the environment.
//
// Usage: node tools/render.js <input.html> <output.png> [scale]
//   scale defaults to 2 (a 1200px-wide poster becomes a 2400px-wide PNG).

const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const [input, output, scaleArg] = process.argv.slice(2);
  if (!input || !output) {
    console.error('Usage: node tools/render.js <input.html> <output.png> [scale]');
    process.exit(1);
  }
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1200, height: 1200 },
    deviceScaleFactor: Number(scaleArg) || 2,
  });
  page.on('pageerror', (err) => console.error('page error:', err.message));
  await page.goto('file://' + path.resolve(input));
  // The page sizes its timer pills and draws the flow arrows once fonts load.
  await page.waitForFunction(() => window.__posterReady === true, null, { timeout: 15000 });
  await page.locator('.poster').screenshot({ path: output });
  await browser.close();
  console.log('wrote', output);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
