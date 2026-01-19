#!/bin/bash
cd /Users/nicholashomyk/mono/AgenticQA
git add .
git commit -m "feat: Add custom pipeline naming with intelligent type defaults

- Add optional pipeline name input to dashboard
- Generate smart defaults: 'AgenticQA - [Pipeline Type]'
- Allow users to specify custom names (up to 255 chars)
- Backend validates pipeline name input
- Updated /api/trigger-workflow to handle custom names
- Fully backward compatible"
git push origin main
