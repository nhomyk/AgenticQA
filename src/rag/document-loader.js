/**
 * Document Loader for RAG
 * Loads and chunks codebase for semantic indexing
 */

const fs = require('fs');
const path = require('path');

class DocumentLoader {
  constructor(config = {}) {
    this.config = {
      rootDir: config.rootDir || process.cwd(),
      extensions: config.extensions || ['.js', '.md', '.json', '.ts'],
      ignorePatterns: config.ignorePatterns || [
        'node_modules',
        '.git',
        'coverage',
        'build',
        'dist',
        '.env',
        '.rag-index'
      ],
      chunkSize: config.chunkSize || 500,
      overlapSize: config.overlapSize || 50,
      maxFileSize: config.maxFileSize || 1000000 // 1MB
    };
  }

  /**
   * Load all documents from codebase
   */
  async loadCodebase() {
    console.log(`📂 Loading codebase from ${this.config.rootDir}...`);

    const documents = [];
    const walk = (dir, depth = 0) => {
      if (depth > 10) return; // Prevent deep recursion

      const entries = fs.readdirSync(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        const relativePath = path.relative(this.config.rootDir, fullPath);

        // Check ignore patterns
        if (this.shouldIgnore(relativePath)) {
          continue;
        }

        if (entry.isDirectory()) {
          walk(fullPath, depth + 1);
        } else if (this.shouldLoadFile(entry.name)) {
          try {
            const stat = fs.statSync(fullPath);
            if (stat.size <= this.config.maxFileSize) {
              const content = fs.readFileSync(fullPath, 'utf8');
              documents.push({
                id: fullPath,
                source: relativePath,
                type: path.extname(entry.name),
                content,
                size: stat.size
              });
            }
          } catch (err) {
            console.warn(`⚠️  Could not read ${relativePath}: ${err.message}`);
          }
        }
      }
    };

    walk(this.config.rootDir);

    console.log(`✅ Loaded ${documents.length} documents`);
    return documents;
  }

  /**
   * Chunk documents for indexing
   */
  chunkDocuments(documents) {
    console.log(`✂️  Chunking ${documents.length} documents...`);

    const chunks = [];
    let totalChunks = 0;

    for (const doc of documents) {
      const lines = doc.content.split('\n');
      let currentChunk = [];
      let chunkNumber = 0;

      for (let i = 0; i < lines.length; i++) {
        currentChunk.push(lines[i]);

        if (currentChunk.length >= this.config.chunkSize) {
          chunks.push({
            id: `${doc.id}#chunk${chunkNumber}`,
            source: doc.source,
            type: doc.type,
            chunk: chunkNumber,
            content: currentChunk.join('\n'),
            startLine: i - currentChunk.length + 1,
            endLine: i
          });

          totalChunks++;

          // Overlap for context continuity
          const overlapLines = currentChunk.slice(-this.config.overlapSize);
          currentChunk = overlapLines;
          chunkNumber++;
        }
      }

      // Add remaining content
      if (currentChunk.length > 0) {
        chunks.push({
          id: `${doc.id}#chunk${chunkNumber}`,
          source: doc.source,
          type: doc.type,
          chunk: chunkNumber,
          content: currentChunk.join('\n'),
          startLine: lines.length - currentChunk.length,
          endLine: lines.length
        });

        totalChunks++;
      }
    }

    console.log(`✅ Created ${totalChunks} chunks (avg ${(totalChunks / documents.length).toFixed(1)} per document)`);
    return chunks;
  }

  /**
   * Load specific files (for updates)
   */
  async loadFiles(filePaths) {
    const documents = [];

    for (const filePath of filePaths) {
      const fullPath = path.join(this.config.rootDir, filePath);

      if (fs.existsSync(fullPath) && this.shouldLoadFile(path.basename(filePath))) {
        const content = fs.readFileSync(fullPath, 'utf8');
        documents.push({
          id: fullPath,
          source: filePath,
          type: path.extname(filePath),
          content,
          size: fs.statSync(fullPath).size
        });
      }
    }

    return documents;
  }

  /**
   * Load markdown documentation
   */
  async loadDocumentation(docDir = 'docs') {
    const docPath = path.join(this.config.rootDir, docDir);

    if (!fs.existsSync(docPath)) {
      return [];
    }

    const documents = [];
    const walk = (dir) => {
      const entries = fs.readdirSync(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory()) {
          walk(fullPath);
        } else if (entry.name.endsWith('.md')) {
          const content = fs.readFileSync(fullPath, 'utf8');
          documents.push({
            id: fullPath,
            source: path.relative(this.config.rootDir, fullPath),
            type: '.md',
            content,
            isDocumentation: true
          });
        }
      }
    };

    walk(docPath);
    return documents;
  }

  /**
   * Check if file should be ignored
   */
  shouldIgnore(filePath) {
    return this.config.ignorePatterns.some(pattern => filePath.includes(pattern));
  }

  /**
   * Check if file should be loaded
   */
  shouldLoadFile(filename) {
    return this.config.extensions.some(ext => filename.endsWith(ext));
  }
}

module.exports = DocumentLoader;
