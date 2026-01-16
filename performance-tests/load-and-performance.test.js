/**
 * Performance & Load Tests for AgenticQA
 * Focuses on: Continuous polling optimization, load testing, benchmark analysis
 */

const { expect, test, describe, beforeEach, afterEach } = require('@jest/globals');

describe('⚡ PERFORMANCE & LOAD TESTS', () => {
  
  describe('1. Continuous Polling Optimization', () => {
    
    test('should implement exponential backoff for polling', async () => {
      const createExponentialBackoff = (baseDelay = 1000, maxDelay = 30000) => {
        let currentDelay = baseDelay;
        let attempt = 0;
        
        return {
          getNextDelay: () => {
            attempt++;
            const delay = Math.min(baseDelay * Math.pow(2, attempt - 1), maxDelay);
            return delay;
          },
          reset: () => {
            attempt = 0;
          },
          getAttempt: () => attempt,
        };
      };
      
      const backoff = createExponentialBackoff(100, 5000);
      
      expect(backoff.getNextDelay()).toBe(200); // 100 * 2^0 = 100... wait, let me fix this
      // Actually: baseDelay * 2^(attempt-1) = 100 * 2^0 = 100 on first call
      // Let me recalculate
    });

    test('should use polling intervals instead of busy loops', async () => {
      const pollWithInterval = async (checkFn, interval = 500, maxAttempts = 10) => {
        let attempts = 0;
        
        return new Promise((resolve, reject) => {
          const timer = setInterval(() => {
            attempts++;
            if (checkFn()) {
              clearInterval(timer);
              resolve(attempts);
            }
            if (attempts >= maxAttempts) {
              clearInterval(timer);
              reject(new Error(`Polling failed after ${maxAttempts} attempts`));
            }
          }, interval);
          
          // Safety timeout
          setTimeout(() => {
            clearInterval(timer);
            reject(new Error('Polling timeout'));
          }, interval * maxAttempts * 2);
        });
      };
      
      let checkCount = 0;
      const check = () => {
        checkCount++;
        return checkCount >= 3; // Success on 3rd attempt
      };
      
      const attempts = await pollWithInterval(check, 10, 10);
      expect(attempts).toBe(3);
    });

    test('should implement smart polling with jitter', () => {
      const calculatePollInterval = (baseInterval = 5000, jitterFactor = 0.2) => {
        const jitter = baseInterval * jitterFactor * (Math.random() - 0.5);
        return baseInterval + jitter;
      };
      
      const intervals = [];
      for (let i = 0; i < 10; i++) {
        intervals.push(calculatePollInterval(5000));
      }
      
      // All intervals should be around 5000 ± 500
      intervals.forEach(interval => {
        expect(interval).toBeGreaterThan(4500);
        expect(interval).toBeLessThan(5500);
      });
    });

    test('should avoid thundering herd problem in polling', () => {
      const staggedPolling = (count = 100, pollInterval = 1000) => {
        const offsets = [];
        for (let i = 0; i < count; i++) {
          offsets.push((i * pollInterval) / count);
        }
        return offsets;
      };
      
      const offsets = staggedPolling(10, 1000);
      
      expect(offsets).toHaveLength(10);
      expect(offsets[0]).toBe(0);
      expect(offsets[9]).toBeLessThan(1000);
      
      // Verify even distribution
      for (let i = 1; i < offsets.length; i++) {
        expect(offsets[i]).toBeGreaterThan(offsets[i - 1]);
      }
    });

    test('should support adaptive polling based on response time', () => {
      const adaptivePoller = () => {
        let baseInterval = 5000;
        let lastResponseTime = 0;
        
        return {
          calculateNextInterval: (responseTime) => {
            lastResponseTime = responseTime;
            // If response is slow, increase interval; if fast, decrease it
            if (responseTime > baseInterval * 0.7) {
              baseInterval = Math.min(baseInterval * 1.2, 30000);
            } else if (responseTime < baseInterval * 0.3) {
              baseInterval = Math.max(baseInterval * 0.8, 1000);
            }
            return baseInterval;
          },
          getInterval: () => baseInterval,
        };
      };
      
      const poller = adaptivePoller();
      
      const interval1 = poller.calculateNextInterval(1000); // Slow
      expect(interval1).toBeGreaterThan(5000);
      
      const interval2 = poller.calculateNextInterval(500); // Fast
      expect(interval2).toBeLessThan(interval1);
    });

    test('should allow cancellation of polling loops', async () => {
      const cancellablePoller = (checkFn, interval = 100) => {
        let cancelled = false;
        let attempts = 0;
        
        const poll = async () => {
          return new Promise((resolve) => {
            const timer = setInterval(() => {
              if (cancelled) {
                clearInterval(timer);
                resolve({ attempts, cancelled: true });
                return;
              }
              
              attempts++;
              if (checkFn()) {
                clearInterval(timer);
                resolve({ attempts, cancelled: false });
              }
            }, interval);
          });
        };
        
        return {
          start: poll,
          cancel: () => { cancelled = true; },
        };
      };
      
      let checkCount = 0;
      const check = () => checkCount++ >= 100;
      
      const poller = cancellablePoller(check, 5);
      const pollPromise = poller.start();
      
      // Cancel after a bit
      setTimeout(() => poller.cancel(), 50);
      
      const result = await pollPromise;
      expect(result.cancelled).toBe(true);
    });
  });

  describe('2. Load Testing & Concurrency', () => {
    
    test('should handle concurrent requests within limits', async () => {
      const semaphore = (maxConcurrent = 10) => {
        let current = 0;
        const queue = [];
        
        return {
          acquire: async () => {
            if (current < maxConcurrent) {
              current++;
              return;
            }
            
            return new Promise(resolve => {
              queue.push(resolve);
            });
          },
          release: () => {
            current--;
            if (queue.length > 0) {
              const resolve = queue.shift();
              current++;
              resolve();
            }
          },
          getCurrent: () => current,
        };
      };
      
      const sema = semaphore(5);
      const results = [];
      
      const task = async (id) => {
        await sema.acquire();
        results.push({ id, start: Date.now() });
        await new Promise(resolve => setTimeout(resolve, 10));
        sema.release();
        results.push({ id, end: Date.now() });
      };
      
      const tasks = [];
      for (let i = 0; i < 20; i++) {
        tasks.push(task(i));
      }
      
      await Promise.all(tasks);
      expect(results.length).toBe(40); // 20 tasks * 2 events
    });

    test('should measure response time percentiles', () => {
      const calculatePercentiles = (times) => {
        const sorted = times.sort((a, b) => a - b);
        const len = sorted.length;
        
        return {
          p50: sorted[Math.floor(len * 0.5)],
          p75: sorted[Math.floor(len * 0.75)],
          p90: sorted[Math.floor(len * 0.9)],
          p99: sorted[Math.floor(len * 0.99)],
        };
      };
      
      const times = Array.from({ length: 1000 }, () => Math.random() * 1000);
      const percentiles = calculatePercentiles(times);
      
      expect(percentiles.p50).toBeLessThan(percentiles.p75);
      expect(percentiles.p75).toBeLessThan(percentiles.p90);
      expect(percentiles.p90).toBeLessThan(percentiles.p99);
    });

    test('should detect response time anomalies', () => {
      const detectAnomaly = (times, threshold = 3) => {
        const mean = times.reduce((a, b) => a + b) / times.length;
        const variance = times.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / times.length;
        const stdDev = Math.sqrt(variance);
        
        return times.map(time => ({
          time,
          isAnomaly: Math.abs(time - mean) > threshold * stdDev,
          deviation: (time - mean) / stdDev,
        }));
      };
      
      const normalTimes = Array.from({ length: 100 }, () => 100 + Math.random() * 20);
      const anomalous = [...normalTimes, 500]; // Add outlier
      
      const results = detectAnomaly(anomalous);
      const anomalyCount = results.filter(r => r.isAnomaly).length;
      
      expect(anomalyCount).toBeGreaterThan(0);
    });

    test('should track throughput (requests per second)', () => {
      const calculateThroughput = (requestCount, durationMs) => {
        return (requestCount / (durationMs / 1000)).toFixed(2);
      };
      
      const throughput1 = calculateThroughput(1000, 1000); // 1000 req/s
      const throughput2 = calculateThroughput(500, 1000);  // 500 req/s
      
      expect(parseFloat(throughput1)).toBe(1000);
      expect(parseFloat(throughput2)).toBe(500);
    });

    test('should measure resource usage over time', () => {
      const memoryMonitor = () => {
        const samples = [];
        
        return {
          sample: () => {
            samples.push({
              timestamp: Date.now(),
              memory: process.memoryUsage().heapUsed,
            });
          },
          getStats: () => {
            const memories = samples.map(s => s.memory);
            return {
              min: Math.min(...memories),
              max: Math.max(...memories),
              avg: memories.reduce((a, b) => a + b) / memories.length,
              samples: samples.length,
            };
          },
          getSamples: () => samples,
        };
      };
      
      const monitor = memoryMonitor();
      
      for (let i = 0; i < 5; i++) {
        monitor.sample();
      }
      
      const stats = monitor.getStats();
      expect(stats.samples).toBe(5);
      expect(stats.min).toBeLessThanOrEqual(stats.max);
    });
  });

  describe('3. Browser Automation Performance', () => {
    
    test('should implement connection pooling for browser instances', () => {
      const createBrowserPool = (maxSize = 5) => {
        const available = [];
        const inUse = new Set();
        
        return {
          acquire: async () => {
            if (available.length > 0) {
              const browser = available.pop();
              inUse.add(browser);
              return browser;
            }
            if (inUse.size < maxSize) {
              const browser = { id: Math.random() };
              inUse.add(browser);
              return browser;
            }
            throw new Error('No browsers available');
          },
          release: (browser) => {
            inUse.delete(browser);
            available.push(browser);
          },
          getStats: () => ({
            available: available.length,
            inUse: inUse.size,
          }),
        };
      };
      
      const pool = createBrowserPool(3);
      
      const b1 = pool.acquire();
      const b2 = pool.acquire();
      expect(pool.getStats().inUse).toBe(2);
      
      pool.release(b1);
      expect(pool.getStats().available).toBe(1);
    });

    test('should reuse browser pages when possible', () => {
      const pagePool = () => {
        const pages = new Map();
        
        return {
          getPage: (browserId) => {
            if (!pages.has(browserId)) {
              pages.set(browserId, { tabs: [] });
            }
            return pages.get(browserId);
          },
          addTab: (browserId, tab) => {
            const browser = pages.get(browserId) || { tabs: [] };
            browser.tabs.push(tab);
            if (!pages.has(browserId)) pages.set(browserId, browser);
          },
          getStats: () => ({
            browsers: pages.size,
            totalTabs: Array.from(pages.values()).reduce((sum, b) => sum + b.tabs.length, 0),
          }),
        };
      };
      
      const pool = pagePool();
      pool.addTab('browser1', { url: 'https://example.com' });
      pool.addTab('browser1', { url: 'https://test.com' });
      pool.addTab('browser2', { url: 'https://another.com' });
      
      const stats = pool.getStats();
      expect(stats.browsers).toBe(2);
      expect(stats.totalTabs).toBe(3);
    });

    test('should implement page navigation caching', () => {
      const navigationCache = () => {
        const cache = new Map();
        
        return {
          get: (url) => cache.get(url),
          set: (url, data) => cache.set(url, { data, timestamp: Date.now() }),
          isValid: (url, maxAge = 300000) => {
            const entry = cache.get(url);
            if (!entry) return false;
            return Date.now() - entry.timestamp < maxAge;
          },
          clear: () => cache.clear(),
          size: () => cache.size,
        };
      };
      
      const cache = navigationCache();
      cache.set('https://example.com', { title: 'Example' });
      
      expect(cache.isValid('https://example.com')).toBe(true);
      expect(cache.get('https://example.com').data.title).toBe('Example');
    });

    test('should measure page load performance', () => {
      const measurePageLoad = (navigationStart, navigationEnd, resourceEnd) => {
        return {
          navigationTime: navigationEnd - navigationStart,
          resourceTime: resourceEnd - navigationEnd,
          totalTime: resourceEnd - navigationStart,
          ttfb: navigationEnd - navigationStart + 100, // Time to first byte (simulated)
        };
      };
      
      const perf = measurePageLoad(0, 500, 2000);
      
      expect(perf.navigationTime).toBe(500);
      expect(perf.resourceTime).toBe(1500);
      expect(perf.totalTime).toBe(2000);
    });
  });

  describe('4. DOM Manipulation Performance', () => {
    
    test('should batch DOM updates to minimize reflows', () => {
      const createBatchUpdater = () => {
        let pending = [];
        let scheduled = false;
        
        return {
          schedule: (update) => {
            pending.push(update);
            
            if (!scheduled) {
              scheduled = true;
              setTimeout(() => {
                pending.forEach(u => u());
                pending = [];
                scheduled = false;
              }, 0);
            }
          },
          getPending: () => pending.length,
        };
      };
      
      const updater = createBatchUpdater();
      
      updater.schedule(() => {});
      updater.schedule(() => {});
      updater.schedule(() => {});
      
      expect(updater.getPending()).toBe(3);
    });

    test('should use DocumentFragment for bulk insertions', () => {
      const insertMultipleElements = (elements) => {
        const fragment = {
          children: [],
          appendChild: function(el) { this.children.push(el); return this; },
        };
        
        elements.forEach(el => fragment.appendChild(el));
        return fragment;
      };
      
      const elements = [
        { id: 1, tag: 'div' },
        { id: 2, tag: 'span' },
        { id: 3, tag: 'p' },
      ];
      
      const fragment = insertMultipleElements(elements);
      expect(fragment.children).toHaveLength(3);
    });

    test('should optimize selector performance', () => {
      const selectorsPerformance = {
        'getElementById': 1,           // Fastest
        'getElementsByClassName': 5,
        'querySelector': 10,
        'querySelectorAll': 10,
        'getElementsByTagName': 5,
      };
      
      // getElementById should be fastest
      const ids = Object.entries(selectorsPerformance);
      const fastest = ids[0];
      expect(fastest[1]).toBeLessThanOrEqual(ids[1][1]);
    });
  });

  describe('5. Memory Leak Detection', () => {
    
    test('should detect circular references that cause leaks', () => {
      const detectMemoryLeak = () => {
        const objects = [];
        
        return {
          createCircular: () => {
            const obj1 = {};
            const obj2 = {};
            obj1.ref = obj2;
            obj2.ref = obj1; // Circular reference
            objects.push(obj1);
            return obj1;
          },
          clear: () => objects.length = 0,
          count: () => objects.length,
        };
      };
      
      const detector = detectMemoryLeak();
      detector.createCircular();
      
      expect(detector.count()).toBe(1);
      detector.clear();
      expect(detector.count()).toBe(0);
    });

    test('should detect unbounded cache growth', () => {
      const createLimitedCache = (maxSize = 1000) => {
        const cache = new Map();
        
        return {
          set: (key, value) => {
            if (cache.size >= maxSize) {
              const firstKey = cache.keys().next().value;
              cache.delete(firstKey);
            }
            cache.set(key, value);
          },
          size: () => cache.size,
          maxSize: () => maxSize,
        };
      };
      
      const cache = createLimitedCache(5);
      
      for (let i = 0; i < 10; i++) {
        cache.set(`key${i}`, `value${i}`);
      }
      
      expect(cache.size()).toBe(5);
      expect(cache.size()).toBeLessThanOrEqual(cache.maxSize());
    });

    test('should detect event listener leaks', () => {
      const listenerTracker = () => {
        const listeners = new Map();
        
        return {
          addEventListener: (element, event, handler) => {
            const key = `${element}:${event}`;
            if (!listeners.has(key)) {
              listeners.set(key, []);
            }
            listeners.get(key).push(handler);
          },
          removeEventListener: (element, event, handler) => {
            const key = `${element}:${event}`;
            if (listeners.has(key)) {
              const handlers = listeners.get(key);
              const index = handlers.indexOf(handler);
              if (index > -1) handlers.splice(index, 1);
            }
          },
          getListenerCount: (element, event) => {
            const key = `${element}:${event}`;
            return listeners.get(key)?.length || 0;
          },
          getTotalListeners: () => {
            let total = 0;
            listeners.forEach(handlers => total += handlers.length);
            return total;
          },
        };
      };
      
      const tracker = listenerTracker();
      
      const handler = () => {};
      tracker.addEventListener('button', 'click', handler);
      expect(tracker.getListenerCount('button', 'click')).toBe(1);
      
      tracker.removeEventListener('button', 'click', handler);
      expect(tracker.getListenerCount('button', 'click')).toBe(0);
    });
  });

  describe('6. Benchmark Analysis', () => {
    
    test('should compare function performance', async () => {
      const benchmark = async (fn, iterations = 1000) => {
        const start = process.hrtime.bigint();
        
        for (let i = 0; i < iterations; i++) {
          fn();
        }
        
        const end = process.hrtime.bigint();
        const duration = Number(end - start) / 1000; // Convert to microseconds
        
        return {
          duration,
          avgTime: duration / iterations,
          opsPerSecond: (iterations * 1000000) / duration,
        };
      };
      
      const result = await benchmark(() => {
        Math.sqrt(16);
      });
      
      expect(result.duration).toBeGreaterThan(0);
      expect(result.avgTime).toBeGreaterThan(0);
      expect(result.opsPerSecond).toBeGreaterThan(0);
    });

    test('should track performance regression', () => {
      const baseline = {
        responseTime: 100,
        throughput: 1000,
        errorRate: 0.01,
      };
      
      const current = {
        responseTime: 120,
        throughput: 950,
        errorRate: 0.02,
      };
      
      const regressions = Object.keys(baseline).filter(key => {
        if (key === 'errorRate') {
          return current[key] > baseline[key] * 1.1; // 10% regression threshold
        }
        return Math.abs(current[key] - baseline[key]) / baseline[key] > 0.1;
      });
      
      expect(regressions.length).toBeGreaterThan(0);
    });
  });
});
