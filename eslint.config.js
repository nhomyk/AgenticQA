// eslint.config.js
export default [
  {
    files: ["**/*.js"],
    ignores: ["node_modules/**", "playwright-tests/**", "unit-tests/**"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
    },
    rules: {
      semi: ["error", "always"],
      quotes: ["error", "double"],
      "no-unused-vars": "warn",
      "no-undef": "error"
    },
  },
];
