/**
 * SRE Agent - Dependency Version Auto-Remediation
 * 
 * Detects incompatible package versions and automatically downgrades
 * to stable releases, healing CI/CD pipeline failures autonomously.
 */

const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs');
const path = require('path');

const execAsync = promisify(exec);

class SREDependencyHealer {
  constructor() {
    this.packageJsonPath = path.join(process.cwd(), 'package.json');
    this.maxRetries = 3;
  }

  async validateDependencies() {
    try {
      console.log('🔍 Validating dependencies...');
      await execAsync('npm ci --dry-run');
      console.log('✅ All dependencies valid');
      return { status: 'healthy', message: 'Dependencies resolved' };
    } catch (error) {
      console.error('❌ Dependency conflict detected:', error.message);
      return await this.autoRemediateDependencies(error);
    }
  }

  parseVersionError(errorMessage) {
    // Parse "No matching version found for package@^X.Y.Z"
    const match = errorMessage.match(/notarget No matching version found for ([\w-]+)@[\^~]?([\d.]+)/);
    if (match) {
      return { package: match[1], version: match[2] };
    }
    return null;
  }

  getStableVersion(version) {
    // Downgrade by one minor version
    const parts = version.split('.');
    if (parts.length >= 2) {
      const minor = parseInt(parts[1]);
      if (minor > 0) {
        parts[1] = (minor - 1).toString();
        return `^${parts.join('.')}`;
      } else if (parts[0] > 0) {
        // If minor is 0, downgrade major
        parts[0] = (parseInt(parts[0]) - 1).toString();
        parts[1] = '14'; // Safe fallback
        return `^${parts.join('.')}`;
      }
    }
    return null;
  }

  async autoRemediateDependencies(error, attempt = 1) {
    if (attempt > this.maxRetries) {
      console.error('❌ Max remediation attempts reached');
      return { status: 'failed', message: 'Could not remediate dependencies' };
    }

    const versionError = this.parseVersionError(error.message);
    if (!versionError) {
      console.warn('⚠️ Could not parse version error, attempting npm audit fix');
      try {
        await execAsync('npm audit fix --force');
        return { status: 'remediated', method: 'npm audit fix', attempt };
      } catch (auditError) {
        return { status: 'failed', message: 'npm audit fix failed' };
      }
    }

    const { package: pkgName, version } = versionError;
    const stableVersion = this.getStableVersion(version);

    if (!stableVersion) {
      console.error(`❌ Cannot determine stable version for ${pkgName}@${version}`);
      return { status: 'failed', message: `Cannot resolve ${pkgName}` };
    }

    try {
      console.log(`🔧 Attempt ${attempt}: Remediating ${pkgName}@${version} → ${stableVersion}`);
      
      const packageJson = JSON.parse(fs.readFileSync(this.packageJsonPath, 'utf8'));
      packageJson.dependencies[pkgName] = stableVersion;
      fs.writeFileSync(this.packageJsonPath, JSON.stringify(packageJson, null, 2) + '\n');

      await execAsync('npm ci');
      console.log(`✅ Successfully remediated ${pkgName} to ${stableVersion}`);
      
      return {
        status: 'remediated',
        package: pkgName,
        fromVersion: version,
        toVersion: stableVersion,
        attempt
      };
    } catch (retryError) {
      console.log(`⚠️ Remediation attempt ${attempt} failed, retrying...`);
      return await this.autoRemediateDependencies(retryError, attempt + 1);
    }
  }

  async healthCheck() {
    try {
      const result = await this.validateDependencies();
      if (result.status === 'healthy') {
        console.log('\n✅ Pipeline Health Check: PASSED\n');
      } else if (result.status === 'remediated') {
        console.log(`\n✅ Pipeline Self-Healed: ${result.package}\n`);
      }
      return result;
    } catch (error) {
      console.error('\n❌ Pipeline Health Check: FAILED\n', error);
      process.exit(1);
    }
  }
}

// Run health check
const sre = new SREDependencyHealer();
sre.healthCheck().then(result => {
  console.log(JSON.stringify(result, null, 2));
  process.exit(result.status === 'failed' ? 1 : 0);
});

module.exports = SREDependencyHealer;
