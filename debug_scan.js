const puppeteer = require('puppeteer');

function mapIssue(type, message, recommendation) {
  return { type, message, recommendation };
}

async function run(target) {
  const results = [];
  let browser;
  try {
    browser = await puppeteer.launch({ headless: false, devtools: true, args: ['--no-sandbox'] });
  } catch (e) {
    console.warn('Default puppeteer launch failed, retrying with system Chrome executable:', e.message || e);
    try {
      browser = await puppeteer.launch({ headless: false, devtools: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args: [] });
    } catch (e2) {
      console.error('Failed to launch system Chrome as well:', e2.message || e2);
      throw e2;
    }
  }
  const page = await browser.newPage();
  page.on('console', msg => {
    try {
      if (msg.type() === 'error') {
        const text = msg.text();
        console.error('PAGE CONSOLE ERROR:', text);
        results.push(mapIssue('ConsoleError', text, 'Check the stack trace and source; fix the script error or wrap calls in try/catch.'));
      } else {
        console.log('PAGE LOG:', msg.type(), msg.text());
      }
    } catch (e) {}
  });

  page.on('pageerror', err => {
    console.error('PAGE ERROR:', err);
    results.push(mapIssue('PageError', String(err), 'Fix the exception in page scripts; guard against undefined values.'));
  });

  page.on('requestfailed', request => {
    console.warn('REQUEST FAILED:', request.url(), request.failure() && request.failure().errorText);
    results.push(mapIssue('RequestFailed', `${request.url()} -> ${request.failure() && request.failure().errorText}`, 'Check resource URL and server responses; ensure CORS and availability.'));
  });

  await page.setViewport({ width: 1280, height: 900 });
  try {
    await page.goto(target, { waitUntil: 'load', timeout: 60000 });
  } catch (e) {
    console.error('NAVIGATION ERROR', e);
    results.push(mapIssue('NavigationError', String(e), 'Verify the URL and network; consider increasing timeout.'));
  }

  const domIssues = await page.evaluate(() => {
    const issues = [];
    document.querySelectorAll('img').forEach(img => {
      if (!img.hasAttribute('alt')) {
        issues.push({ type: 'MissingAlt', message: `img src=${img.currentSrc || img.src} missing alt`, recommendation: 'Add meaningful alt text describing the image.' });
      } else if (img.getAttribute('alt').trim() === '') {
        issues.push({ type: 'EmptyAlt', message: `img src=${img.currentSrc || img.src} has empty alt`, recommendation: 'Provide descriptive alt text or mark as decorative with alt="" and role="presentation".' });
      }
      if (img.naturalWidth === 0) {
        issues.push({ type: 'BrokenImage', message: `img src=${img.currentSrc || img.src} appears broken (naturalWidth=0)`, recommendation: 'Ensure the image URL is correct and the resource is served.' });
      }
    });
    document.querySelectorAll('input, textarea, select').forEach(el => {
      const id = el.id;
      const hasLabel = id && document.querySelector(`label[for="${id}"]`);
      const aria = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
      if (!hasLabel && !aria && el.type !== 'hidden') {
        issues.push({ type: 'MissingLabel', message: `Form control (${el.tagName.toLowerCase()} type=${el.type || 'n/a'}) missing label or aria-label`, recommendation: 'Add a <label> or aria-label to improve accessibility.' });
      }
    });
    document.querySelectorAll('a').forEach(a => {
      const href = a.getAttribute('href');
      if (!href || href.trim() === '' || href === '#') {
        issues.push({ type: 'BadHref', message: `anchor text="${(a.textContent||'').trim().slice(0,30)}" has href="${href}"`, recommendation: 'Use meaningful hrefs or use button elements for actions.' });
      }
    });
    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(h => parseInt(h.tagName.slice(1)));
    for (let i = 1; i < headings.length; i++) {
      if (headings[i] > headings[i-1] + 1) {
        issues.push({ type: 'HeadingOrder', message: `Possible heading order issue: ...${headings[i-1]} -> ${headings[i]}`, recommendation: 'Ensure heading levels follow a logical sequence for accessibility and structure.' });
        break;
      }
    }
    return issues;
  });

  domIssues.forEach(i => results.push(mapIssue(i.type, i.message, i.recommendation)));

  const trimmed = results.slice(0, 25);
  console.log(JSON.stringify({ url: target, results: trimmed, totalFound: results.length }, null, 2));

  console.log('\nBrowser open for debugging. Press ENTER in this terminal to close the browser and exit.');
  process.stdin.setRawMode(false);
  process.stdin.resume();
  process.stdin.once('data', async () => {
    await browser.close();
    process.exit(0);
  });
}

const target = process.argv[2] || 'https://example.com';
run(target).catch(err => { console.error(err); process.exit(1); });
