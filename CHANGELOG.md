# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-01-12

### Added
- **Security Testing**: Added npm audit, secrets scanning, and SAST analysis to CI/CD
- **Open-Source Foundation**: Added LICENSE (MIT), CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- **Production Readiness**: 
  - Input validation and sanitization
  - Rate limiting on API endpoints
  - Environment-based configuration
  - Comprehensive error handling
  - Docker support
- **Technology Detection**: Enhanced detection to 6 methods (scripts, meta, links, headers, patterns, libraries)
- **SRE Agent**: Improved local error detection and automatic fixing with detailed logging

### Changed
- Improved ESLint configuration with security rules
- Enhanced error messages for better debugging
- Better logging output in production mode

### Fixed
- Resolved quote style violations in code
- Fixed Cypress test structure issues
- Improved test script formatting in package.json

### Security
- Added dependency vulnerability scanning
- Added secrets detection in CI/CD
- Implemented CORS protection
- Added input validation and XSS prevention

## [0.1.3] - 2026-01-12

### Added
- Improved SRE agent with local error detection
- Better handling of ESLint errors

## [0.1.2] - 2026-01-12

### Added
- Enhanced technology detection with 6 detection methods

## [0.1.1] - 2026-01-12

### Added
- Iterative test-driven code repairs (max 3 iterations)
- Test failure log parsing
- Fixed Cypress test suite

## [0.1.0] - 2026-01-10

### Added
- Initial release
- Basic web scanning functionality
- Support for multiple test frameworks
- GitHub Actions CI/CD pipeline
- SRE automation agent
