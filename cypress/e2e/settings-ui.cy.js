describe('Settings Page - RAG Configuration UI', () => {
  beforeEach(() => {
    cy.visit('http://localhost:3000/settings');
    // Clear localStorage before each test
    cy.clearLocalStorage();
  });

  describe('Page Load & Layout', () => {
    it('should load the settings page with all sections', () => {
      cy.get('.header h1').should('contain', '🚀 AgenticQA Settings');
      cy.get('.header p').should('contain', 'Configure RAG');
      cy.get('.settings-card').should('have.length.greaterThan', 2);
    });

    it('should display navigation tabs', () => {
      cy.get('.tabs').should('exist');
      cy.get('.tab').should('have.length', 3);
      cy.get('.tab').contains('Embeddings').should('exist');
      cy.get('.tab').contains('API Keys').should('exist');
      cy.get('.tab').contains('Advanced').should('exist');
    });

    it('should have Embeddings tab active by default', () => {
      cy.get('.tab').first().should('have.class', 'active');
      cy.get('#embeddings').should('have.class', 'active');
    });
  });

  describe('Embeddings Tab', () => {
    it('should display embedding provider dropdown', () => {
      cy.get('#embeddingProvider').should('exist');
      cy.get('#embeddingProvider option').should('have.length', 3);
      cy.get('#embeddingProvider').should('have.value', 'local');
    });

    it('should show local settings when provider is local', () => {
      cy.get('#embeddingProvider').select('local');
      cy.get('#localSettings').should('be.visible');
      cy.get('#openaiSettings').should('not.be.visible');
    });

    it('should show OpenAI settings when provider is OpenAI', () => {
      cy.get('#embeddingProvider').select('openai');
      cy.get('#openaiSettings').should('be.visible');
      cy.get('#localSettings').should('not.be.visible');
    });

    it('should display HuggingFace model selection grid', () => {
      cy.get('#modelGrid').should('exist');
      cy.get('.model-card').should('have.length', 3);
    });

    it('should select MiniLM model by default', () => {
      cy.get('.model-card').first().should('have.class', 'selected');
    });

    it('should allow model selection', () => {
      cy.get('.model-card').eq(1).click();
      cy.get('.model-card').eq(1).should('have.class', 'selected');
      cy.get('.model-card').first().should('not.have.class', 'selected');
    });

    it('should display model specifications', () => {
      cy.get('.model-card').first().within(() => {
        cy.get('.model-name').should('contain', 'MiniLM');
        cy.get('.model-specs').should('contain', '⚡');
        cy.get('.model-specs').should('contain', '384D');
      });
    });

    it('should show local embeddings benefits', () => {
      cy.get('.provider-info').should('contain', 'Local Embeddings Benefits');
      cy.get('.provider-info').should('contain', '$0');
      cy.get('.provider-info').should('contain', 'private');
    });

    it('should save embedding settings', () => {
      cy.get('#embeddingProvider').select('local');
      cy.get('.model-card').eq(1).click();
      cy.get('button').contains('Save Embedding Settings').click();
    });
  });

  describe('API Keys Tab', () => {
    beforeEach(() => {
      cy.get('.tab').contains('API Keys').click();
    });

    it('should switch to API Keys tab', () => {
      cy.get('#keys').should('have.class', 'active');
      cy.get('#embeddings').should('not.have.class', 'active');
    });

    it('should display OpenAI API key input', () => {
      cy.get('#apiKeyOpenAI').should('exist');
      cy.get('#apiKeyOpenAI').should('have.attr', 'type', 'password');
    });

    it('should display Pinecone API key input', () => {
      cy.get('#apiKeyPinecone').should('exist');
      cy.get('#apiKeyPinecone').should('have.attr', 'type', 'password');
    });

    it('should toggle password visibility for OpenAI key', () => {
      cy.get('#apiKeyOpenAI').type('sk-test123');
      cy.get('button').contains('Show/Hide').first().click();
      cy.get('#apiKeyOpenAI').should('have.attr', 'type', 'text');
      cy.get('#apiKeyOpenAI').should('have.value', 'sk-test123');
    });

    it('should display security warning', () => {
      cy.get('.warning-box').should('contain', 'Security Notice');
      cy.get('.warning-box').should('contain', 'never sent to our servers');
    });

    it('should save API keys', () => {
      cy.get('#apiKeyOpenAI').type('sk-test123');
      cy.get('#apiKeyPinecone').type('pc-test456');
      cy.get('button').contains('Save API Keys').click();
    });
  });

  describe('Advanced Tab', () => {
    beforeEach(() => {
      cy.get('.tab').contains('Advanced').click();
    });

    it('should display advanced settings inputs', () => {
      cy.get('#maxTokens').should('exist');
      cy.get('#topK').should('exist');
      cy.get('#minRelevance').should('exist');
      cy.get('#enableCaching').should('exist');
      cy.get('#cacheSize').should('exist');
    });

    it('should have default values', () => {
      cy.get('#maxTokens').should('have.value', '8191');
      cy.get('#topK').should('have.value', '5');
      cy.get('#minRelevance').should('have.value', '0.7');
      cy.get('#cacheSize').should('have.value', '100');
    });

    it('should update topK value', () => {
      cy.get('#topK').clear().type('10');
      cy.get('#topK').should('have.value', '10');
    });

    it('should toggle caching', () => {
      cy.get('#enableCaching').uncheck();
      cy.get('#enableCaching').should('not.be.checked');
      cy.get('#enableCaching').check();
      cy.get('#enableCaching').should('be.checked');
    });

    it('should save advanced settings', () => {
      cy.get('#topK').clear().type('8');
      cy.get('button').contains('Save Advanced Settings').click();
    });

    it('should reset to defaults', () => {
      cy.get('#topK').clear().type('15');
      cy.get('button').contains('Reset to Defaults').click();
      cy.on('window:confirm', () => true);
    });
  });

  describe('Configuration Summary', () => {
    it('should display current configuration', () => {
      cy.get('#configSummary').should('exist');
      cy.get('#configSummary').should('contain', 'Active Embedding Provider');
      cy.get('#configSummary').should('contain', 'Model');
      cy.get('#configSummary').should('contain', 'RAG Context');
    });

    it('should update summary when settings change', () => {
      cy.get('#embeddingProvider').select('openai');
      cy.get('#configSummary').should('contain', 'OPENAI');
    });
  });

  describe('Cost Calculator', () => {
    beforeEach(() => {
      cy.get('#embeddingProvider').select('openai');
    });

    it('should display cost calculator for OpenAI', () => {
      cy.get('.cost-calculator').should('be.visible');
    });

    it('should calculate cost for 1000 queries', () => {
      cy.get('#queriesPerMonth').clear().type('1000');
      cy.get('#queriesPerMonth').trigger('change');
      cy.get('#costResult').should('contain', '0.03');
    });

    it('should calculate cost for 10000 queries', () => {
      cy.get('#queriesPerMonth').clear().type('10000');
      cy.get('#queriesPerMonth').trigger('change');
      cy.get('#costResult').invoke('text').then((text) => {
        const cost = parseFloat(text);
        expect(cost).to.be.greaterThan(0.29);
      });
    });
  });

  describe('Model Specifications', () => {
    it('should display MiniLM model specs', () => {
      cy.get('.model-card').eq(0).should('contain', '⚡ Fast');
      cy.get('.model-card').eq(0).should('contain', '384D');
      cy.get('.model-card').eq(0).should('contain', '22MB');
    });

    it('should display MPNet model specs', () => {
      cy.get('.model-card').eq(1).should('contain', 'Balanced');
      cy.get('.model-card').eq(1).should('contain', '768D');
      cy.get('.model-card').eq(1).should('contain', '438MB');
    });

    it('should display E5 model specs', () => {
      cy.get('.model-card').eq(2).should('contain', 'Multilingual');
      cy.get('.model-card').eq(2).should('contain', '768D');
    });
  });

  describe('Responsive Design', () => {
    it('should be responsive on mobile', () => {
      cy.viewport('iphone-x');
      cy.get('.container').should('be.visible');
      cy.get('.settings-card').should('be.visible');
      cy.get('.model-grid').should('be.visible');
    });

    it('should be responsive on tablet', () => {
      cy.viewport('ipad-2');
      cy.get('.settings-card').should('be.visible');
      cy.get('.tabs').should('be.visible');
    });

    it('should be responsive on desktop', () => {
      cy.viewport(1920, 1080);
      cy.get('.container').should('have.css', 'max-width', '900px');
    });
  });

  describe('Data Persistence', () => {
    it('should persist embedding provider selection', () => {
      cy.get('#embeddingProvider').select('openai');
      cy.get('button').contains('Save Embedding Settings').click();
      cy.reload();
      cy.get('#embeddingProvider').should('have.value', 'openai');
    });

    it('should persist model selection', () => {
      cy.get('.model-card').eq(1).click();
      cy.get('button').contains('Save Embedding Settings').click();
      cy.reload();
      cy.get('.model-card').eq(1).should('have.class', 'selected');
    });

    it('should persist API keys', () => {
      cy.get('.tab').contains('API Keys').click();
      cy.get('#apiKeyOpenAI').type('sk-test123');
      cy.get('button').contains('Save API Keys').click();
      cy.reload();
      cy.get('.tab').contains('API Keys').click();
      cy.get('#apiKeyOpenAI').should('have.value', 'sk-test123');
    });

    it('should persist advanced settings', () => {
      cy.get('.tab').contains('Advanced').click();
      cy.get('#topK').clear().type('8');
      cy.get('button').contains('Save Advanced Settings').click();
      cy.reload();
      cy.get('.tab').contains('Advanced').click();
      cy.get('#topK').should('have.value', '8');
    });
  });

  describe('Error Handling', () => {
    it('should validate OpenAI key format', () => {
      cy.get('#embeddingProvider').select('openai');
      cy.get('#openaiKey').type('invalid-key');
      cy.get('.btn-test').first().click();
      cy.get('#openaiStatus').should('contain', 'Invalid');
    });

    it('should show error on invalid topK', () => {
      cy.get('.tab').contains('Advanced').click();
      cy.get('#topK').clear().type('25');
      cy.get('#topK').invoke('attr', 'max').then((max) => {
        expect(parseInt(max)).to.be.lessThan(25);
      });
    });

    it('should validate minRelevance range', () => {
      cy.get('.tab').contains('Advanced').click();
      cy.get('#minRelevance').invoke('attr', 'min').should('equal', '0');
      cy.get('#minRelevance').invoke('attr', 'max').should('equal', '1');
    });
  });

  describe('UI Elements Styling', () => {
    it('should have proper button styling', () => {
      cy.get('.btn-primary').should('have.css', 'background');
      cy.get('.btn-secondary').should('have.css', 'background');
    });

    it('should have proper status indicator colors', () => {
      cy.get('.status-indicator.active').should('have.css', 'background-color');
      cy.get('.status-indicator.inactive').should('have.css', 'background-color');
    });

    it('should highlight selected model card', () => {
      cy.get('.model-card.selected').should('have.css', 'border-color');
    });
  });

  describe('Accessibility', () => {
    it('should have proper heading hierarchy', () => {
      cy.get('h1').should('exist');
      cy.get('.section-title').should('exist');
    });

    it('should have descriptive labels for all inputs', () => {
      cy.get('label').should('have.length.greaterThan', 5);
    });

    it('should have keyboard navigation', () => {
      cy.get('#embeddingProvider').focus();
      cy.get('#embeddingProvider').should('be.focused');
    });
  });
});
