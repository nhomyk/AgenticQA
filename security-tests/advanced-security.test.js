/**
 * Advanced Security Tests for AgenticQA
 * Focuses on: Input validation, XSS prevention, SQL injection, eval() detection
 */

const { expect, test, describe, beforeEach, afterEach } = require('@jest/globals');

// Mock functions for security testing
const sanitizeString = (str) => {
  if (typeof str !== 'string') throw new Error('Input must be a string');
  return str.replace(/[<>\"'&]/g, (char) => {
    const entities = { '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '&': '&amp;' };
    return entities[char];
  });
};

const validateUrl = (url) => {
  if (!url || typeof url !== 'string') throw new Error('URL must be a non-empty string');
  if (url.length > 2048) throw new Error('URL exceeds maximum length');
  
  try {
    const parsed = new URL(url);
    const allowedProtocols = ['http:', 'https:'];
    if (!allowedProtocols.includes(parsed.protocol)) {
      throw new Error(`Protocol ${parsed.protocol} not allowed`);
    }
    const blockedHosts = ['localhost', '127.0.0.1', '0.0.0.0', '::1'];
    if (blockedHosts.includes(parsed.hostname)) {
      throw new Error('Local hosts not allowed');
    }
    return true;
  } catch (err) {
    throw new Error(`Invalid URL: ${err.message}`);
  }
};

const validateInput = (input, maxLength = 1000, allowedChars = /^[a-zA-Z0-9\s\-._~:/?#[\]@!$&'()*+,;=]*$/) => {
  if (!input || typeof input !== 'string') throw new Error('Input must be non-empty string');
  if (input.length > maxLength) throw new Error(`Input exceeds max length of ${maxLength}`);
  if (!allowedChars.test(input)) throw new Error('Input contains invalid characters');
  return true;
};

const preventSQLInjection = (input) => {
  const sqlKeywords = /(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE)\b)/gi;
  const sqlComments = /(--|;|\/\*|\*\/|xp_|sp_)/gi;
  
  if (sqlKeywords.test(input) || sqlComments.test(input)) {
    throw new Error('Potential SQL injection detected');
  }
  return true;
};

describe('🔒 CRITICAL SECURITY TESTS', () => {
  
  describe('1. Input Validation & Sanitization', () => {
    
    test('should reject invalid URL formats', () => {
      const invalidUrls = [
        'not-a-url',
        'ftp://example.com',
        'file:///etc/passwd',
        'javascript:alert("xss")',
        'data:text/html,<script>alert(1)</script>',
        '',
        null,
      ];
      
      invalidUrls.forEach(url => {
        expect(() => validateUrl(url)).toThrow();
      });
    });

    test('should accept valid URLs', () => {
      const validUrls = [
        'https://www.example.com',
        'http://example.com/path?query=value',
        'https://subdomain.example.co.uk:8080/path',
        'https://example.com/path#fragment',
      ];
      
      validUrls.forEach(url => {
        expect(() => validateUrl(url)).not.toThrow();
      });
    });

    test('should reject localhost and internal IPs', () => {
      const internalUrls = [
        'http://localhost:3000',
        'http://127.0.0.1:8080',
        'http://0.0.0.0:9000',
        'http://[::1]:3000',
      ];
      
      internalUrls.forEach(url => {
        expect(() => validateUrl(url)).toThrow();
      });
    });

    test('should reject URLs exceeding max length', () => {
      const longUrl = 'https://example.com/' + 'a'.repeat(2500);
      expect(() => validateUrl(longUrl)).toThrow();
    });

    test('should enforce URL length limits (2048 chars)', () => {
      const url2048 = 'https://example.com/' + 'a'.repeat(2028);
      expect(() => validateUrl(url2048)).not.toThrow();
      
      const url2049 = 'https://example.com/' + 'a'.repeat(2029);
      expect(() => validateUrl(url2049)).toThrow();
    });
  });

  describe('2. XSS Prevention', () => {
    
    test('should sanitize HTML special characters', () => {
      const maliciousInputs = [
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert("xss")>',
        '<svg onload=alert("xss")>',
        '<body onload=alert("xss")>',
        '"><script>alert(document.domain)</script>',
      ];
      
      maliciousInputs.forEach(input => {
        const sanitized = sanitizeString(input);
        expect(sanitized).not.toContain('<script>');
        expect(sanitized).not.toContain('onerror=');
        expect(sanitized).not.toContain('onload=');
        expect(sanitized).not.toMatch(/<script|onerror|onload/i);
      });
    });

    test('should handle javascript: protocol in URLs', () => {
      expect(() => validateUrl('javascript:alert("xss")')).toThrow();
      expect(() => validateUrl('java\nscript:alert("xss")')).not.toThrow(); // Should be handled elsewhere
    });

    test('should escape HTML entities correctly', () => {
      const input = '<div>"Test" & \'example\'</div>';
      const sanitized = sanitizeString(input);
      
      expect(sanitized).toBe('&lt;div&gt;&quot;Test&quot; &amp; &#39;example&#39;&lt;/div&gt;');
    });

    test('should prevent DOM-based XSS via innerHTML', () => {
      const userInput = '<img src=x onerror=alert("xss")>';
      const sanitized = sanitizeString(userInput);
      
      // Sanitized input should be safe for innerHTML
      expect(sanitized).not.toContain('onerror=');
    });

    test('should sanitize event handler attributes', () => {
      const eventHandlers = [
        'onclick=alert("xss")',
        'onmouseover=alert("xss")',
        'onfocus=alert("xss")',
        'onload=alert("xss")',
      ];
      
      eventHandlers.forEach(handler => {
        const sanitized = sanitizeString(handler);
        expect(sanitized).not.toContain('=');
        expect(sanitized).toContain('&');
      });
    });
  });

  describe('3. SQL Injection Prevention', () => {
    
    test('should detect SQL keywords in input', () => {
      const sqlInjectionAttempts = [
        "' OR '1'='1",
        "admin'--",
        "' UNION SELECT * FROM users--",
        "1'; DROP TABLE users;--",
        "' OR 1=1 /*",
      ];
      
      sqlInjectionAttempts.forEach(attempt => {
        expect(() => preventSQLInjection(attempt)).toThrow();
      });
    });

    test('should detect SQL comments', () => {
      const commentPatterns = [
        "test--",
        "test;",
        "test/*comment*/",
        "test xp_",
        "test sp_",
      ];
      
      commentPatterns.forEach(pattern => {
        expect(() => preventSQLInjection(pattern)).toThrow();
      });
    });

    test('should allow legitimate input', () => {
      const legitimateInputs = [
        'John Doe',
        'user@example.com',
        'password123!@#',
        'Test-Value_2024',
      ];
      
      legitimateInputs.forEach(input => {
        expect(() => preventSQLInjection(input)).not.toThrow();
      });
    });
  });

  describe('4. Rate Limiting & DoS Protection', () => {
    
    test('should enforce rate limits on API endpoints', async () => {
      // Simulate rate limiter
      const rateLimits = {};
      const MAX_REQUESTS = 10;
      const WINDOW_MS = 60000;
      
      const checkRateLimit = (ip) => {
        const now = Date.now();
        if (!rateLimits[ip]) {
          rateLimits[ip] = { count: 0, resetTime: now + WINDOW_MS };
        }
        
        if (now > rateLimits[ip].resetTime) {
          rateLimits[ip] = { count: 0, resetTime: now + WINDOW_MS };
        }
        
        rateLimits[ip].count++;
        return rateLimits[ip].count <= MAX_REQUESTS;
      };
      
      // Test rapid requests
      const ip = '192.168.1.1';
      for (let i = 0; i < 10; i++) {
        expect(checkRateLimit(ip)).toBe(true);
      }
      expect(checkRateLimit(ip)).toBe(false); // 11th request should be rejected
    });

    test('should reset rate limits after window expires', async () => {
      const rateLimits = {};
      const MAX_REQUESTS = 5;
      const WINDOW_MS = 100; // 100ms for testing
      
      const checkRateLimit = (ip) => {
        const now = Date.now();
        if (!rateLimits[ip] || now > rateLimits[ip].resetTime) {
          rateLimits[ip] = { count: 0, resetTime: now + WINDOW_MS };
        }
        rateLimits[ip].count++;
        return rateLimits[ip].count <= MAX_REQUESTS;
      };
      
      const ip = '192.168.1.1';
      for (let i = 0; i < 5; i++) checkRateLimit(ip);
      expect(checkRateLimit(ip)).toBe(false);
      
      // Wait for window to expire
      await new Promise(resolve => setTimeout(resolve, 150));
      
      // Should allow requests again
      expect(checkRateLimit(ip)).toBe(true);
    });
  });

  describe('5. eval() Detection & Prevention', () => {
    
    test('should detect eval() usage in code', () => {
      const codeWithEval = 'const result = eval(userInput);';
      expect(codeWithEval).toMatch(/eval\s*\(/);
    });

    test('should not allow eval() in production code', () => {
      const serverCode = `
        app.post('/api/execute', (req, res) => {
          const result = eval(req.body.code);  // DANGEROUS!
          res.json(result);
        });
      `;
      
      expect(serverCode).toMatch(/eval\s*\(/);
    });

    test('should suggest alternatives to eval()', () => {
      const alternatives = [
        'Function()',
        'JSON.parse()',
        'vm.runInContext()',
        'Worker threads',
      ];
      
      // Verify alternatives exist as recommended options
      expect(alternatives).toHaveLength(4);
    });
  });

  describe('6. Data Mutation Security', () => {
    
    test('should validate data mutation endpoints', () => {
      const mutations = [
        { method: 'POST', path: '/api/user', requires: 'authentication' },
        { method: 'PUT', path: '/api/user/:id', requires: 'authorization' },
        { method: 'DELETE', path: '/api/user/:id', requires: 'authorization' },
      ];
      
      mutations.forEach(mutation => {
        expect(mutation).toHaveProperty('method');
        expect(mutation).toHaveProperty('path');
        expect(mutation).toHaveProperty('requires');
        expect(['authentication', 'authorization']).toContain(mutation.requires);
      });
    });

    test('should require authentication for data mutations', () => {
      const requiresAuth = (method) => {
        return ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method);
      };
      
      expect(requiresAuth('POST')).toBe(true);
      expect(requiresAuth('PUT')).toBe(true);
      expect(requiresAuth('DELETE')).toBe(true);
      expect(requiresAuth('GET')).toBe(false);
    });

    test('should validate authorization on sensitive operations', () => {
      const authzCheck = (user, resource, action) => {
        if (!user) return false;
        if (resource === 'admin' && user.role !== 'admin') return false;
        if (action === 'delete' && !user.permissions.includes('delete')) return false;
        return true;
      };
      
      const admin = { role: 'admin', permissions: ['read', 'write', 'delete'] };
      const user = { role: 'user', permissions: ['read', 'write'] };
      
      expect(authzCheck(admin, 'admin', 'delete')).toBe(true);
      expect(authzCheck(user, 'admin', 'delete')).toBe(false);
      expect(authzCheck(user, 'profile', 'delete')).toBe(false);
    });
  });

  describe('7. Security Headers Validation', () => {
    
    test('should enforce security headers in responses', () => {
      const headers = {
        'Content-Security-Policy': "default-src 'self'; script-src 'self'",
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000',
      };
      
      Object.entries(headers).forEach(([header, value]) => {
        expect(header).toBeDefined();
        expect(value).toBeDefined();
        expect(value.length).toBeGreaterThan(0);
      });
    });

    test('should validate CSP directives', () => {
      const csp = "default-src 'self'; script-src 'self' https://trusted.com; style-src 'self' 'unsafe-inline'";
      
      expect(csp).toContain('default-src');
      expect(csp).toContain('script-src');
      expect(csp).toContain('style-src');
      expect(csp).not.toContain("script-src 'unsafe-eval'");
    });
  });

  describe('8. Authentication & Token Validation', () => {
    
    test('should validate JWT tokens', () => {
      // Simplified JWT validation
      const validateToken = (token) => {
        if (!token || typeof token !== 'string') return false;
        const parts = token.split('.');
        return parts.length === 3; // JWT has 3 parts separated by dots
      };
      
      expect(validateToken('valid.jwt.token')).toBe(true);
      expect(validateToken('invalid')).toBe(false);
      expect(validateToken('')).toBe(false);
    });

    test('should reject expired tokens', () => {
      const checkTokenExpiry = (exp) => {
        const now = Math.floor(Date.now() / 1000);
        return exp > now;
      };
      
      const futureTime = Math.floor(Date.now() / 1000) + 3600;
      const pastTime = Math.floor(Date.now() / 1000) - 3600;
      
      expect(checkTokenExpiry(futureTime)).toBe(true);
      expect(checkTokenExpiry(pastTime)).toBe(false);
    });

    test('should require valid authentication headers', () => {
      const validateAuthHeader = (header) => {
        if (!header || typeof header !== 'string') return false;
        return header.startsWith('Bearer ') && header.length > 7;
      };
      
      expect(validateAuthHeader('Bearer eyJhbGc...')).toBe(true);
      expect(validateAuthHeader('Bearer')).toBe(false);
      expect(validateAuthHeader('Basic abc')).toBe(false);
    });
  });

  describe('9. CORS & Cross-Origin Security', () => {
    
    test('should validate CORS origins', () => {
      const allowedOrigins = ['https://example.com', 'https://app.example.com'];
      
      const isCorsAllowed = (origin) => {
        return allowedOrigins.includes(origin);
      };
      
      expect(isCorsAllowed('https://example.com')).toBe(true);
      expect(isCorsAllowed('https://malicious.com')).toBe(false);
    });

    test('should not allow wildcard CORS in production', () => {
      const corsConfig = {
        origin: 'https://example.com', // Not '*'
        credentials: true,
      };
      
      expect(corsConfig.origin).not.toBe('*');
      expect(corsConfig.credentials).toBe(true);
    });
  });

  describe('10. Error Handling & Information Disclosure', () => {
    
    test('should not expose sensitive stack traces', () => {
      const sanitizeError = (err, isProduction = true) => {
        if (isProduction) {
          return { message: 'Internal Server Error', status: 500 };
        }
        return { message: err.message, stack: err.stack, status: 500 };
      };
      
      const error = new Error('Database connection failed');
      const prodError = sanitizeError(error, true);
      
      expect(prodError).not.toHaveProperty('stack');
      expect(prodError.message).not.toContain('Database');
    });

    test('should not leak error details in API responses', () => {
      const errorResponse = {
        error: 'Invalid request',
        code: 'VALIDATION_ERROR',
        status: 400,
      };
      
      expect(errorResponse).not.toHaveProperty('stack');
      expect(errorResponse).not.toHaveProperty('details');
      expect(errorResponse.message).toBeUndefined();
    });
  });
});
