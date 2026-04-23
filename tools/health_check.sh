#!/bin/bash
# tools/health_check.sh
# SAF System Health Check Script
# Referenced in: docs/DEPLOYMENT.md

echo "SAF System Health Check"
echo "======================="

# Check LogBook integrity
if [ -d "LogBook" ]; then
  echo "✅ LogBook directory exists"
else
  echo "❌ LogBook directory missing"
fi

# Check configuration
if python3 -c "import yaml; yaml.safe_load(open('integration/config/saf.integration.yaml'))" 2>/dev/null; then
  echo "✅ Integration config valid"
else
  echo "❌ Integration config invalid"
fi

# Check GitHub Actions status
if command -v gh &> /dev/null; then
  if gh run list --limit 1 --json conclusion --jq '.[0].conclusion' 2>/dev/null | grep -q "success"; then
    echo "✅ Latest workflow passed"
  else
    echo "⚠️  Latest workflow failed or pending"
  fi
else
  echo "⚠️  GitHub CLI (gh) not installed - skipping workflow check"
fi

echo "======================="
