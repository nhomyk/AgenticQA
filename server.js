const express = require("express");
const bodyParser = require("body-parser");
const puppeteer = require("puppeteer");
const path = require("path");

            { name: "React", pattern: /react/i },
            { name: "Angular", pattern: /angular/i },
            { name: "Vue", pattern: /vue(\.js)?/i },
            { name: "Svelte", pattern: /svelte/i },
            { name: "Next.js", pattern: /next(\.js)?/i },
            { name: "Nuxt.js", pattern: /nuxt(\.js)?/i },
            { name: "Gatsby", pattern: /gatsby/i },
            { name: "Ember", pattern: /ember/i },
            { name: "Preact", pattern: /preact/i },
            { name: "jQuery", pattern: /jquery/i },
            { name: "Backbone", pattern: /backbone/i },
            { name: "Alpine.js", pattern: /alpine(\.js)?/i },
            { name: "Bootstrap", pattern: /bootstrap/i },
            { name: "Tailwind CSS", pattern: /tailwind/i },
            { name: "Bulma", pattern: /bulma/i },
            { name: "Material UI", pattern: /material[- ]?ui/i },
            { name: "Chakra UI", pattern: /chakra[- ]?ui/i },
            { name: "Express", pattern: /express/i },
            { name: "Koa", pattern: /koa/i },
            { name: "Fastify", pattern: /fastify/i },
            { name: "NestJS", pattern: /nestjs/i },
            { name: "Django", pattern: /django/i },
            { name: "Flask", pattern: /flask/i },
            { name: "Rails", pattern: /rails/i },
            { name: "Laravel", pattern: /laravel/i },
            { name: "Spring", pattern: /spring/i },
            { name: "ASP.NET", pattern: /asp\.net/i },
            { name: "WordPress", pattern: /wordpress/i },
            { name: "Drupal", pattern: /drupal/i },
            { name: "Magento", pattern: /magento/i },
            { name: "Shopify", pattern: /shopify/i },
            { name: "Squarespace", pattern: /squarespace/i },
            { name: "Wix", pattern: /wix/i },
            { name: "Babel", pattern: /babel/i },
            { name: "Webpack", pattern: /webpack/i },
            { name: "Parcel", pattern: /parcel/i },
            { name: "Vite", pattern: /vite/i },
            { name: "Rollup", pattern: /rollup/i },
            { name: "Grunt", pattern: /grunt/i },
            { name: "Gulp", pattern: /gulp/i },
            { name: "Mocha", pattern: /mocha/i },
            { name: "Jest", pattern: /jest/i },
            { name: "Cypress", pattern: /cypress/i },
            { name: "Playwright", pattern: /playwright/i },
            { name: "Vitest", pattern: /vitest/i },
            { name: "Jasmine", pattern: /jasmine/i },
            { name: "Testing Library", pattern: /testing[- ]?library/i },
            { name: "Puppeteer", pattern: /puppeteer/i },
            { name: "Nightmare", pattern: /nightmare/i },
            { name: "Selenium", pattern: /selenium/i },
            { name: "QUnit", pattern: /qunit/i },
            { name: "AVA", pattern: /ava/i },
            { name: "Chai", pattern: /chai/i },
            { name: "Sinon", pattern: /sinon/i },
            { name: "Enzyme", pattern: /enzyme/i },
            { name: "Storybook", pattern: /storybook/i },
            { name: "Redux", pattern: /redux/i },
            { name: "MobX", pattern: /mobx/i },
            { name: "RxJS", pattern: /rxjs/i },
            { name: "Apollo", pattern: /apollo/i },
            { name: "GraphQL", pattern: /graphql/i },
            { name: "Socket.io", pattern: /socket\.io/i },
            { name: "D3.js", pattern: /d3(\.js)?/i },
            { name: "Chart.js", pattern: /chart(\.js)?/i },
            { name: "Three.js", pattern: /three(\.js)?/i },
            { name: "PixiJS", pattern: /pixijs/i },
            { name: "GSAP", pattern: /gsap/i },
            { name: "Anime.js", pattern: /anime(\.js)?/i },
            { name: "Lodash", pattern: /lodash/i },
            { name: "Underscore", pattern: /underscore/i },
            { name: "Moment.js", pattern: /moment(\.js)?/i },
            { name: "Day.js", pattern: /day(\.js)?/i },
            { name: "Date-fns", pattern: /date[- ]?fns/i },
            { name: "Ramda", pattern: /ramda/i },
            { name: "Immutable.js", pattern: /immutable(\.js)?/i },
            { name: "Bluebird", pattern: /bluebird/i },
            { name: "Axios", pattern: /axios/i },
            { name: "Superagent", pattern: /superagent/i },
            { name: "Fetch", pattern: /fetch/i },
            { name: "jQuery Ajax", pattern: /jquery\.ajax/i },
            { name: "XMLHttpRequest", pattern: /xmlhttprequest/i },
            { name: "SocketCluster", pattern: /socketcluster/i },
            { name: "FeathersJS", pattern: /feathers/i },
            { name: "Meteor", pattern: /meteor/i },
            { name: "Parse", pattern: /parse/i },
            { name: "Firebase", pattern: /firebase/i },
            { name: "AWS Amplify", pattern: /amplify/i },
            { name: "Netlify", pattern: /netlify/i },
            { name: "Vercel", pattern: /vercel/i },
            { name: "Heroku", pattern: /heroku/i },
            { name: "Glitch", pattern: /glitch/i },
            { name: "Surge", pattern: /surge/i },
            { name: "Render", pattern: /render/i },
            { name: "DigitalOcean", pattern: /digitalocean/i },
            { name: "Linode", pattern: /linode/i },
            { name: "Vultr", pattern: /vultr/i },
            { name: "OVH", pattern: /ovh/i },
            { name: "Hetzner", pattern: /hetzner/i },
            { name: "Cloudflare", pattern: /cloudflare/i },
            { name: "Fastly", pattern: /fastly/i },
            { name: "Akamai", pattern: /akamai/i },
            { name: "Google Cloud", pattern: /google cloud/i },
            { name: "AWS", pattern: /aws/i },
            { name: "Azure", pattern: /azure/i },
            { name: "IBM Cloud", pattern: /ibm cloud/i },
            { name: "Oracle Cloud", pattern: /oracle cloud/i },
            { name: "Salesforce", pattern: /salesforce/i },
            { name: "SAP", pattern: /sap/i },
            { name: "ServiceNow", pattern: /servicenow/i },
            { name: "Atlassian", pattern: /atlassian/i },
            { name: "Slack", pattern: /slack/i },
            { name: "Twilio", pattern: /twilio/i },
            { name: "SendGrid", pattern: /sendgrid/i },
            { name: "Mailgun", pattern: /mailgun/i },
            { name: "Mailchimp", pattern: /mailchimp/i },
            { name: "Stripe", pattern: /stripe/i },
            { name: "PayPal", pattern: /paypal/i },
            { name: "Square", pattern: /square/i },
            { name: "Plaid", pattern: /plaid/i },
            { name: "Auth0", pattern: /auth0/i },
            { name: "Okta", pattern: /okta/i },
            { name: "OneLogin", pattern: /onelogin/i },
            { name: "Ping Identity", pattern: /ping identity/i },
            { name: "Duo", pattern: /duo/i },
            { name: "HashiCorp", pattern: /hashicorp/i },
            { name: "Terraform", pattern: /terraform/i },
            { name: "Ansible", pattern: /ansible/i },
            { name: "Chef", pattern: /chef/i },
            { name: "Puppet", pattern: /puppet/i },
            { name: "SaltStack", pattern: /saltstack/i },
            { name: "Kubernetes", pattern: /kubernetes/i },
            { name: "Docker", pattern: /docker/i },
            { name: "Podman", pattern: /podman/i },
            { name: "OpenShift", pattern: /openshift/i },
            { name: "Rancher", pattern: /rancher/i },
            { name: "Nomad", pattern: /nomad/i },
            { name: "Consul", pattern: /consul/i },
            { name: "Vault", pattern: /vault/i },
            { name: "Prometheus", pattern: /prometheus/i },
            { name: "Grafana", pattern: /grafana/i },
            { name: "ELK Stack", pattern: /elk stack|elasticsearch|logstash|kibana/i },
            { name: "Splunk", pattern: /splunk/i },
            { name: "Datadog", pattern: /datadog/i },
            { name: "New Relic", pattern: /new relic/i },
            { name: "Sentry", pattern: /sentry/i },
            { name: "PagerDuty", pattern: /pagerduty/i },
            { name: "Opsgenie", pattern: /opsgenie/i },
            { name: "VictorOps", pattern: /victorops/i },
            { name: "Statuspage", pattern: /statuspage/i },
            { name: "Pingdom", pattern: /pingdom/i },
            { name: "UptimeRobot", pattern: /uptimerobot/i },
            { name: "Better Uptime", pattern: /better uptime/i },
            { name: "Freshping", pattern: /freshping/i },
            { name: "Uptrends", pattern: /uptrends/i },
            { name: "Site24x7", pattern: /site24x7/i },
            { name: "AppDynamics", pattern: /appdynamics/i },
            { name: "Dynatrace", pattern: /dynatrace/i },
            { name: "Instana", pattern: /instana/i },
            { name: "LogicMonitor", pattern: /logicmonitor/i },
            { name: "ScienceLogic", pattern: /sciencelogic/i },
            { name: "Zabbix", pattern: /zabbix/i },
            { name: "Nagios", pattern: /nagios/i },
            { name: "Icinga", pattern: /icinga/i },
            { name: "Centreon", pattern: /centreon/i },
            { name: "PRTG", pattern: /prtg/i },
            { name: "SolarWinds", pattern: /solarwinds/i },
            { name: "ManageEngine", pattern: /manageengine/i },
            { name: "WhatsUp Gold", pattern: /whatsup gold/i },
            { name: "Checkmk", pattern: /checkmk/i },
            { name: "OpenNMS", pattern: /opennms/i },
            { name: "LibreNMS", pattern: /librenms/i },
            { name: "Observium", pattern: /observium/i },
            { name: "Netdata", pattern: /netdata/i }

      // images missing alt or empty alt
      document.querySelectorAll("img").forEach(img => {
        if (!img.hasAttribute("alt")) {
          issues.push({ type: "MissingAlt", message: `img src=${img.currentSrc || img.src} missing alt`, recommendation: "Add meaningful alt text describing the image." });
        } else if (img.getAttribute("alt").trim() === "") {
          issues.push({ type: "EmptyAlt", message: `img src=${img.currentSrc || img.src} has empty alt`, recommendation: "Provide descriptive alt text or mark as decorative with alt=\"\" and role=\"presentation\"." });
        }
        if (img.naturalWidth === 0) {
          issues.push({ type: "BrokenImage", message: `img src=${img.currentSrc || img.src} appears broken (naturalWidth=0)`, recommendation: "Ensure the image URL is correct and the resource is served." });
        }
      });

      // inputs without labels or aria-label
      document.querySelectorAll("input, textarea, select").forEach(el => {
        const id = el.id;
        const hasLabel = id && document.querySelector(`label[for="${id}"]`);
        const aria = el.getAttribute("aria-label") || el.getAttribute("aria-labelledby");
        if (!hasLabel && !aria && el.type !== "hidden") {
          issues.push({ type: "MissingLabel", message: `Form control (${el.tagName.toLowerCase()} type=${el.type || "n/a"}) missing label or aria-label`, recommendation: "Add a <label> or aria-label to improve accessibility." });
        }
      });

      // anchors with empty or javascript href
      document.querySelectorAll("a").forEach(a => {
        const href = a.getAttribute("href");
        if (!href || href.trim() === "" || href === "#") {
          issues.push({ type: "BadHref", message: `anchor text="${(a.textContent||"").trim().slice(0,30)}" has href="${href}"`, recommendation: "Use meaningful hrefs or use button elements for actions." });
        }
      });

      // headings order issues (simple check)
      const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6")).map(h => parseInt(h.tagName.slice(1)));
      for (let i = 1; i < headings.length; i++) {
        if (headings[i] > headings[i-1] + 1) {
          issues.push({ type: "HeadingOrder", message: `Possible heading order issue: ...${headings[i-1]} -> ${headings[i]}`, recommendation: "Ensure heading levels follow a logical sequence for accessibility and structure." });
          break;
        }
      }

      // API usage detection (fetch/XHR)
      const origFetch = window.fetch;
      window.__apiCalls = [];
      window.fetch = function(...args) {
        window.__apiCalls.push(args[0]);
        return origFetch.apply(this, args);
      };
      const origXhrOpen = window.XMLHttpRequest && window.XMLHttpRequest.prototype.open;
      if (origXhrOpen) {
        window.XMLHttpRequest.prototype.open = function(method, url, ...rest) {
          window.__apiCalls.push(url);
          return origXhrOpen.call(this, method, url, ...rest);
        };
      }

      // Wait a bit to collect API calls (simulate page activity)
      return new Promise(resolve => {
        setTimeout(() => {
          const apis = (window.__apiCalls || []).slice(0, 10);
          resolve({ issues, features, apis });
        }, 2000);
      });
    });


    // domResult is now a Promise result
    const { issues: domIssues, features, apis } = domResult;
    domIssues.forEach(i => results.push(mapIssue(i.type, i.message, i.recommendation)));

    // Performance / JMeter-like summary using resource timings
    const perf = await page.evaluate(() => {
      const resources = performance.getEntriesByType("resource").map(r => ({ name: r.name, duration: r.duration, initiatorType: r.initiatorType }));
      const nav = performance.getEntriesByType("navigation")[0] || {};
      const loadTime = nav.loadEventEnd || (performance.timing ? (performance.timing.loadEventEnd - performance.timing.fetchStart) : 0);
      return { resources, loadTime };
    });

    const resourceCount = perf.resources.length;
    const avgResponseTimeMs = resourceCount ? Math.round(perf.resources.reduce((s, r) => s + (r.duration || 0), 0) / resourceCount) : 0;
    const loadTimeMs = Math.round(perf.loadTime || 0);
    const throughputReqPerSec = loadTimeMs > 0 ? Math.round((totalRequests / (loadTimeMs / 1000)) * 100) / 100 : 0;

    const topResources = perf.resources.sort((a,b) => (b.duration||0) - (a.duration||0)).slice(0,10).map(r => ({ name: r.name, timeMs: Math.round(r.duration || 0), type: r.initiatorType }));

    const performanceResults = {
      totalRequests,
      failedRequests,
      resourceCount,
      avgResponseTimeMs,
      loadTimeMs,
      throughputReqPerSec,
      topResources
    };

    // generate recommended test cases (10 positive, 10 negative) based on features
    const testCases = [];
    const f = features;
    // helper to push up to 20
    const pushIf = (title) => { if (testCases.length < 20) testCases.push(title); };

    // Positive tests
    if (f.headingCount > 0) pushIf("Positive: Verify main headings render properly");
    if (f.hasNav) pushIf("Positive: Navigation menu loads and links are clickable");
    if (f.hasSearch) pushIf("Positive: Search returns results for valid query");
    if (f.hasForm) pushIf("Positive: Submitting form with valid data succeeds");
    if (f.hasLogin) pushIf("Positive: Login form accepts valid credentials and redirects");
    if (f.hasImages) pushIf("Positive: Important images display with non-empty alt text");
    if (f.hasButtons) pushIf("Positive: Primary CTA button is visible and triggers action");
    if (f.hasLinks) pushIf("Positive: All main links navigate to expected destinations");
    if (f.hasTables) pushIf("Positive: Data tables render rows and pagination works");
    if (f.hasModal) pushIf("Positive: Modal/dialog opens and closes correctly");

    // Negative tests
    if (f.hasSearch) pushIf("Negative: Searching with gibberish returns no results handled gracefully");
    if (f.hasForm) pushIf("Negative: Submitting form with invalid data shows validation errors");
    if (f.hasLogin) pushIf("Negative: Login with wrong credentials shows proper error");
    if (f.hasImages) pushIf("Negative: Broken image placeholders are shown or replaced");
    if (f.hasButtons) pushIf("Negative: Disabled buttons are not clickable and show correct state");
    if (f.hasLinks) pushIf("Negative: Broken links return 4xx/5xx and are reported");
    pushIf("Negative: Page handles slow network (resources time out)");
    pushIf("Negative: Layout does not break under long text or large images");
    pushIf("Negative: Accessibility: focus order works for keyboard navigation");
    pushIf("Negative: Heading structure regressions cause screen-reader confusion");

    // Generate AI recommendations based on scan results
    const recommendations = generateRecommendations(results, features, performanceResults);

    // Detect technologies
    const technologies = await detectTechnologies(page);
    // Support old and new return format for backward compatibility
    let technologiesArr = [];
    let technologyUrls = [];
    if (technologies && Array.isArray(technologies.techs)) {
      technologiesArr = technologies.techs;
      technologyUrls = technologies.urls;
    } else if (Array.isArray(technologies)) {
      technologiesArr = technologies;
    }
    console.log("[SERVER] Technologies detected for", target, ":", technologiesArr, technologyUrls);

    // trim to 25 issue results
    const trimmed = results.slice(0, 25);

    await browser.close();
    const responsePayload = { url: target, results: trimmed, totalFound: results.length, testCases: testCases.slice(0,20), performanceResults, apis: apis || [], recommendations, technologies: technologiesArr, technologyUrls };
    console.log("[SERVER] Responding with payload:", JSON.stringify(responsePayload, null, 2));
    res.json(responsePayload);
  } catch (err) {
    if (browser) await browser.close();
    res.status(500).json({ error: String(err), results: results.slice(0,25) });
  }
});

const PORT = process.env.PORT || 3000;
if (require.main === module) {
  app.listen(PORT, () => console.log(`Agentic QA Engineer running on http://localhost:${PORT}`));
}

// Export functions for testing (CommonJS)
module.exports = { normalizeUrl, mapIssue };
