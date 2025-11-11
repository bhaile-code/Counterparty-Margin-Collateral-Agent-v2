/**
 * CSV Template Generator Utility
 * Generates and downloads collateral CSV template
 */

/**
 * Generate and download collateral CSV template
 */
export function downloadCSVTemplate(): void {
  const headers = [
    'description',
    'market_value',
    'maturity_min',
    'maturity_max',
    'currency',
    'valuation_scenario',
  ].join(',');

  const examples = [
    // Short-term Treasury
    'US short-term Treasury,,1,USD,No Rating Event,1000000',
    // Mid-term Treasury with specific range
    'US 5-10 year Treasury Note,5,10,USD,No Rating Event,2000000',
    // Long-term bond
    'Fannie Mae long-term bond,10,,USD,Moodys Second Trigger,500000',
    // Corporate bond with specific range
    'Corporate bond - Apple Inc,3,5,USD,,250000',
    // Cash collateral (all maturities)
    'Cash collateral,,,USD,No Rating Event,100000',
  ];

  const csvContent = headers + '\n' + examples.join('\n');

  // Create blob and download
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'collateral_template.csv';
  link.style.display = 'none';

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

/**
 * Get template instructions for display
 */
export function getTemplateInstructions(): string {
  return `
CSV Template Instructions:

Required Columns:
  - description: Description of the collateral (required)
  - market_value: Current market value in USD (required)

Optional Columns:
  - maturity_min: Minimum years to maturity (leave blank for no lower bound)
  - maturity_max: Maximum years to maturity (leave blank for no upper bound)
  - currency: Currency code (default: USD)
  - valuation_scenario: Rating event/trigger (default: first scenario in CSA)

Maturity Range Examples:
  - "1,3" = 1 to 3 years
  - ",1" = less than or equal to 1 year
  - "10," = 10 years or more
  - "," = all maturities (uses most conservative haircut)
  - "5,5" = exactly 5 years

Notes:
  - The system will use AI to match your descriptions to the CSA's eligible collateral
  - If no haircut is found, it defaults to 0% with a warning
  - You can manually override any matched values after import
  `.trim();
}

/**
 * Validate CSV file before upload
 */
export function validateCSVFile(file: File): { valid: boolean; error?: string } {
  // Check file extension
  if (!file.name.toLowerCase().endsWith('.csv')) {
    return {
      valid: false,
      error: 'File must be a CSV file (.csv extension)',
    };
  }

  // Check file size (max 10MB)
  const maxSize = 10 * 1024 * 1024; // 10MB
  if (file.size > maxSize) {
    return {
      valid: false,
      error: 'File size must be less than 10MB',
    };
  }

  // Check file is not empty
  if (file.size === 0) {
    return {
      valid: false,
      error: 'File is empty',
    };
  }

  return { valid: true };
}

/**
 * Format maturity range for display
 */
export function formatMaturityRange(
  min?: number | null,
  max?: number | null
): string {
  if (min === null && max === null) {
    return 'All maturities';
  } else if (min === null || min === undefined) {
    return `≤ ${max} years`;
  } else if (max === null || max === undefined) {
    return `≥ ${min} years`;
  } else if (min === max) {
    return `${min} years`;
  } else {
    return `${min}-${max} years`;
  }
}
