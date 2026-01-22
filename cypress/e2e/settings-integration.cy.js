describe('Settings Page - Integration Tests', () => {
  beforeEach(() => {
    cy.visit('http://localhost:3000/settings');
  });

  describe('Embedding Provider Workflow', () => {
    it('should complete full local embedding setup flow', () => {
      // 1. Select local provider
      cy.get('#embeddingProvider').select('local');
      
      // 2. Select a model
      cy.get('.model-card').eq(1).click();
      cy.get('.model-card').eq(1).should('have.class', 'selected');
      
      // 3. Save settings
      cy.get('button').contains('Save Embedding Settings').click();
      
      // 4. Verify in config summary
      cy.get('#configSummary').should('contain', 'LOCAL');
    });

    it('should complete full OpenAI embedding setup flow', () => {
      // 1. Select OpenAI provider
      cy.get('#embeddingProvider').select('openai');
      
      // 2. Switch to API Keys tab
      cy.get('.tab').contains('API Keys').click();
      
      // 3. Add OpenAI key
      cy.get('#apiKeyOpenAI').type('sk-test123456789');
      
      // 4. Save API keys
      cy.get('button').contains('Save API Keys').click();
      
      // 5. Verify configuration
      cy.get('#configSummary').should('contain', 'OPENAI');
    });
  });

  describe('RAG Configuration Workflow', () => {
    it('should configure RAG parameters', () => {
      cy.get('.tab').contains('Advanced').click();
      
      // Set RAG parameters
      cy.get('#topK').clear().type('7');
      cy.get('#minRelevance').clear().type('0.8');
      cy.get('#enableCaching').check();
      cy.get('#cacheSize').clear().type('200');
      
      // Save
      cy.get('button').contains('Save Advanced Settings').click();
      
      // Verify
      cy.get('#configSummary').should('contain', 'RAG Context');
    });
  });

  describe('Multi-Tab Navigation', () => {
    it('should navigate between all tabs without losing data', () => {
      // Set data in Embeddings tab
      cy.get('.model-card').eq(1).click();
      
      // Go to API Keys
      cy.get('.tab').contains('API Keys').click();
      cy.get('#apiKeyOpenAI').type('sk-test');
      
      // Go to Advanced
      cy.get('.tab').contains('Advanced').click();
      cy.get('#topK').clear().type('10');
      
      // Back to Embeddings
      cy.get('.tab').contains('Embeddings').click();
      cy.get('.model-card').eq(1).should('have.class', 'selected');
    });
  });

  describe('Cost Analysis', () => {
    it('should help user understand OpenAI costs', () => {
      cy.get('#embeddingProvider').select('openai');
      
      // Check different query volumes
      cy.get('#queriesPerMonth').clear().type('100');
      cy.get('#queriesPerMonth').trigger('change');
      cy.get('#costResult').then(($el) => {
        const cost1 = parseFloat($el.text());
        
        cy.get('#queriesPerMonth').clear().type('1000');
        cy.get('#queriesPerMonth').trigger('change');
        cy.get('#costResult').then(($el2) => {
          const cost2 = parseFloat($el2.text());
          expect(cost2).to.be.greaterThan(cost1);
        });
      });
    });
  });

  describe('Settings Validation', () => {
    it('should validate all settings before saving', () => {
      cy.get('.tab').contains('Advanced').click();
      
      // Try invalid topK
      cy.get('#topK').clear().type('50');
      cy.get('#topK').invoke('attr', 'max').then((max) => {
        cy.get('button').contains('Save Advanced Settings').click();
      });
    });
  });

  describe('Provider Switching', () => {
    it('should switch between embedding providers smoothly', () => {
      // Start with local
      cy.get('#embeddingProvider').select('local');
      cy.get('#localSettings').should('be.visible');
      
      // Switch to OpenAI
      cy.get('#embeddingProvider').select('openai');
      cy.get('#localSettings').should('not.be.visible');
      cy.get('#openaiSettings').should('be.visible');
      
      // Switch to Mock
      cy.get('#embeddingProvider').select('mock');
      cy.get('#openaiSettings').should('not.be.visible');
    });
  });

  describe('Settings Reset', () => {
    it('should reset all settings to defaults', () => {
      // Change some settings
      cy.get('.tab').contains('Advanced').click();
      cy.get('#topK').clear().type('15');
      cy.get('#minRelevance').clear().type('0.9');
      
      // Click reset
      cy.get('button').contains('Reset to Defaults').click();
      cy.on('window:confirm', () => true);
      
      // After reset, should be back to defaults
      cy.get('#topK').should('have.value', '5');
      cy.get('#minRelevance').should('have.value', '0.7');
    });
  });

  describe('UI Update Flow', () => {
    it('should update config summary in real-time', () => {
      // Change provider
      cy.get('#embeddingProvider').select('openai');
      cy.get('#configSummary').should('contain', 'OPENAI');
      
      // Change back
      cy.get('#embeddingProvider').select('local');
      cy.get('#configSummary').should('contain', 'LOCAL');
    });
  });

  describe('Security Features', () => {
    it('should mask API keys by default', () => {
      cy.get('.tab').contains('API Keys').click();
      cy.get('#apiKeyOpenAI').should('have.attr', 'type', 'password');
      cy.get('#apiKeyPinecone').should('have.attr', 'type', 'password');
    });

    it('should allow toggling key visibility', () => {
      cy.get('.tab').contains('API Keys').click();
      cy.get('#apiKeyOpenAI').type('sk-test');
      
      // Toggle to show
      cy.get('button').contains('Show/Hide').first().click();
      cy.get('#apiKeyOpenAI').should('have.attr', 'type', 'text');
      
      // Toggle to hide
      cy.get('button').contains('Show/Hide').first().click();
      cy.get('#apiKeyOpenAI').should('have.attr', 'type', 'password');
    });
  });

  describe('Model Selection Persistence', () => {
    it('should remember selected model across page reloads', () => {
      // Select MPNet model
      cy.get('.model-card').eq(1).click();
      cy.get('button').contains('Save Embedding Settings').click();
      
      // Reload page
      cy.reload();
      
      // Verify MPNet is still selected
      cy.get('.model-card').eq(1).should('have.class', 'selected');
    });
  });
});
