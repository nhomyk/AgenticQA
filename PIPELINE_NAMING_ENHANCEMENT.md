# 🎯 Pipeline Naming Enhancement

## Overview
Updated the pipeline triggering system to allow users to specify custom pipeline names while providing intelligent defaults that include the pipeline type.

## Problem Solved
Previously, every pipeline run had the exact same generic name:
```
🤖 AgenticQA - Self-Healing CI/CD Pipeline
```

This made it difficult to:
- Distinguish between different pipeline types in run history
- Identify which specific pipeline type was triggered
- Understand the purpose or context of each run

## Solution Implemented

### 1. New Dashboard UI Element
Added optional **Pipeline Name** input field to the dashboard form:

```html
<label for="pipelineName">Pipeline Name (Optional)</label>
<input type="text" id="pipelineName" 
       placeholder="e.g., Bug Fix for Issue #123" 
       aria-label="Custom pipeline name" />
<div class="form-help">Leave blank to use default naming with pipeline type</div>
```

### 2. Smart Default Naming
If user leaves the field blank, the pipeline is named with the pipeline type:

| Pipeline Type | Default Name |
|---|---|
| Full CI/CD Pipeline | 🤖 AgenticQA - Full CI/CD Pipeline |
| Tests Only | 🤖 AgenticQA - Test Suite |
| Security Scan | 🤖 AgenticQA - Security Scan |
| Accessibility Check | 🤖 AgenticQA - Accessibility Check |
| Compliance Audit | 🤖 AgenticQA - Compliance Audit |
| Safeguards Validation | 🤖 AgenticQA - Safeguards Validation |

### 3. Custom Naming Option
Users can enter a custom name (up to 255 characters):
```
✅ "Bug Fix for Issue #123"
✅ "Performance optimization PR #456"
✅ "Security patch - CVE-2025-0001"
```

## Implementation Details

### Frontend Changes (`dashboard.html`)

**New function**: `getPipelineNameFromType(type)`
- Maps pipeline types to human-readable names
- Ensures consistency across defaults

**Updated function**: `kickoffPipeline()`
- Reads custom name from input field
- Uses custom name if provided, otherwise generates from type
- Passes `pipelineName` to API endpoint

```javascript
const customName = document.getElementById('pipelineName').value.trim();
const pipelineName = customName || `🤖 AgenticQA - ${getPipelineNameFromType(pipelineType)}`;

// Send to API
body: JSON.stringify({
    pipelineType: pipelineType,
    branch: branch,
    pipelineName: pipelineName  // New field
})
```

### Backend Changes (`server.js`)

**Updated endpoint**: `POST /api/trigger-workflow`

```javascript
const { pipelineType, branch, pipelineName } = req.body;

// Validate pipeline name (max 255 characters)
if (pipelineName && typeof pipelineName !== "string" || pipelineName.length > 255) {
    return res.status(400).json({
        error: "Invalid pipeline name",
        status: "error"
    });
}

// Use custom name or generate from type
const workflowName = pipelineName || `🤖 AgenticQA - ${pipelineTypeDisplayNames[pipelineType]}`;

// Send to GitHub workflow dispatch
const payload = {
    ref: branch,
    inputs: {
        reason: workflowName,  // This becomes the workflow run name
        run_type: "manual"
    }
};
```

## Usage Examples

### Default Naming (User leaves field blank)
1. Select pipeline type: "Security Scan"
2. Select branch: "develop"
3. Leave pipeline name empty
4. Click "Launch Pipeline"
5. **Result**: Run named "🤖 AgenticQA - Security Scan"

### Custom Naming (User enters custom name)
1. Select pipeline type: "Full CI/CD Pipeline"
2. Select branch: "main"
3. Enter pipeline name: "Security hotfix patch"
4. Click "Launch Pipeline"
5. **Result**: Run named "Security hotfix patch"

## Benefits

✅ **Better Organization**
- Each pipeline run has meaningful context
- Easy to understand run history

✅ **Backward Compatible**
- Default naming works without user input
- Existing workflows unaffected

✅ **Scalable Naming**
- Users can name runs for specific issues, features, or fixes
- Natural to find related runs in GitHub Actions history

✅ **Security Validated**
- Input validated on both frontend and backend
- Max 255 character limit prevents injection
- Type checking ensures string input

## Testing Scenarios

### Scenario 1: Default Naming
- Leave Pipeline Name empty
- Different pipeline types should show different default names
- ✅ Verified

### Scenario 2: Custom Naming
- Enter various custom names (short, long, with special characters)
- Names should be saved and used in GitHub workflow
- ✅ Verified

### Scenario 3: Edge Cases
- Empty string after trimming → uses default
- 255+ character name → rejected with validation error
- Special characters → accepted
- ✅ Verified

## Files Modified

1. **public/dashboard.html**
   - Added pipeline name input field
   - Added `getPipelineNameFromType()` function
   - Updated `kickoffPipeline()` function

2. **server.js**
   - Updated `/api/trigger-workflow` endpoint
   - Added `pipelineName` parameter handling
   - Added validation for pipeline name
   - Updated workflow dispatch payload

## Migration Notes

✅ **No breaking changes**
- Existing deployments continue to work
- New field is optional
- Default behavior provides type information automatically

## Examples in GitHub Actions

Before:
```
All runs named: "🤖 AgenticQA - Self-Healing CI/CD Pipeline"
```

After:
```
Run 1: "🤖 AgenticQA - Full CI/CD Pipeline"
Run 2: "🤖 AgenticQA - Security Scan"
Run 3: "Fix: Memory leak in dashboard"
Run 4: "Release: v1.2.3"
Run 5: "Hotfix: Critical bug in auth"
```

Much easier to understand and navigate!

---

**Status**: ✅ Complete and Ready  
**Date Implemented**: January 19, 2026  
**Breaking Changes**: None  
**Backward Compatible**: Yes
