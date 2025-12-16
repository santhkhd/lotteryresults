// Node.js script to generate a manifest of available result files in the note folder
// This will output a file called result_manifest.json with metadata for each result

const fs = require('fs');
const path = require('path');

const NOTE_DIR = path.join(__dirname, 'note');
const MANIFEST_FILE = path.join(__dirname, 'result_manifest.json');

function parseResultFilename(filename) {
  // Example: SK-17-2025-08-29.json
  const match = filename.match(/^([A-Z]{2,3})-(\d+)-(\d{4}-\d{2}-\d{2})\.json$/);
  if (!match) return null;
  return {
    code: match[1],
    draw_number: match[2],
    date: match[3],
    filename
  };
}

fs.readdir(NOTE_DIR, (err, files) => {
  if (err) throw err;
  const manifest = files
    .filter(f => f.endsWith('.json'))
    .map(parseResultFilename)
    .filter(entry => {
      if (!entry) return false;

      // 1. Filter out future dates (Strict)
      const entryDate = new Date(entry.date);
      const today = new Date();
      // Reset time to just compare dates
      entryDate.setHours(0, 0, 0, 0);
      today.setHours(0, 0, 0, 0);

      if (entryDate > today) return false;

      // 2. Filter out results with empty prizes or placeholders
      try {
        const content = fs.readFileSync(path.join(NOTE_DIR, entry.filename), 'utf8');
        const data = JSON.parse(content);

        // Prizes is normally an object now { "1st_prize": ... }, check keys
        if (!data.prizes || (Array.isArray(data.prizes) && data.prizes.length === 0) || (typeof data.prizes === 'object' && Object.keys(data.prizes).length === 0)) {
          return false;
        }

        // Double check for placeholder "Please wait" or similar invalid data if wanted
        // but empty prizes check usually suffices for future stubs
      } catch (e) {
        console.error(`Error reading ${entry.filename}:`, e);
        return false;
      }

      return true;
    });
  // Sort by date descending
  manifest.sort((a, b) => {
    // Handle date comparison properly
    const dateA = new Date(a.date);
    const dateB = new Date(b.date);

    // Invalid dates go to the end
    if (isNaN(dateA) && isNaN(dateB)) return 0;
    if (isNaN(dateA)) return 1;
    if (isNaN(dateB)) return -1;

    return dateB - dateA;
  });

  // Remove duplicate entries for the same date, keeping the most recent one
  const uniqueManifest = [];
  const seenDates = new Set();

  for (const entry of manifest) {
    const key = `${entry.date}-${entry.code}`;
    if (seenDates.has(key)) {
      // Skip duplicate entries for same lottery on same date
      continue;
    }
    seenDates.add(key);
    uniqueManifest.push(entry);
  }

  fs.writeFileSync(MANIFEST_FILE, JSON.stringify(uniqueManifest, null, 2));
  console.log(`Manifest written to ${MANIFEST_FILE} with ${uniqueManifest.length} results.`);
});