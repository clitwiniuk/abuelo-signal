// Test session classification logic (Spain time to Eastern time)
function isEasternDST(date) {
  const year = date.getUTCFullYear();
  const march = new Date(Date.UTC(year, 2, 1));
  const november = new Date(Date.UTC(year, 10, 1));

  const secondSundayMarch = new Date(march);
  secondSundayMarch.setUTCDate(march.getUTCDate() + (14 - march.getUTCDay()));

  const firstSundayNovember = new Date(november);
  firstSundayNovember.setUTCDate(november.getUTCDate() + (7 - november.getUTCDay()));

  return date >= secondSundayMarch && date < firstSundayNovember;
}

function convertToEasternTime(spainDateTime) {
   // If input doesn't have timezone, assume it's Spain local time
   let spainDate;
   if (spainDateTime.includes('Z') || spainDateTime.includes('+')) {
     spainDate = new Date(spainDateTime);
   } else {
     // Assume Spain local time, convert to UTC by adding offset
     spainDate = new Date(spainDateTime + '+02:00'); // CEST
   }

   // spainDate is now correctly in UTC
   const utcDate = spainDate;

   const inDST = isEasternDST(utcDate);
   const easternOffset = inDST ? -4 : -5;

   const easternMs = utcDate.getTime() + (easternOffset * 60 * 60 * 1000);
   const easternDate = new Date(easternMs);

   return {
     hours: easternDate.getUTCHours(),
     minutes: easternDate.getUTCMinutes(),
     day: easternDate.getUTCDay()
   };
}

function determineTradingSession(entryTime) {
  const easternTime = convertToEasternTime(entryTime);
  const { hours, minutes } = easternTime;

  // Session boundaries (hardcoded for testing)
  const preStartTime = 4.0; // 04:00
  const preEndTime = 9.5; // 09:30
  const openTime = 9.5; // 09:30
  const closeTime = 16.0; // 16:00
  const afterStartTime = 16.0; // 16:00
  const afterEndTime = 20.0; // 20:00

  const currentTime = hours + (minutes / 60);

  if (currentTime >= preStartTime && currentTime < preEndTime) {
    return 'premarket';
  } else if (currentTime >= openTime && currentTime < (openTime + 1)) {
    return 'first_hour';
  } else if (currentTime >= (openTime + 1) && currentTime < (closeTime - 1)) {
    return 'midday';
  } else if (currentTime >= (closeTime - 1) && currentTime < closeTime) {
    return 'power_hour';
  } else if (currentTime >= afterStartTime && currentTime < afterEndTime) {
    return 'afterhours';
  } else {
    return 'regular_hours';
  }
}

// Test cases for October 2025 (Spain time to Eastern time)
console.log('=== Testing Session Classification (October 2025 - Spain to Eastern) ===');

// Premarket: 04:00-09:30 Eastern = 06:00-11:30 UTC = 08:00-13:30 Spain
console.log('Premarket (08:00 Spain):', determineTradingSession('2025-10-12T08:00:00')); // Should be premarket

// First hour: 09:30-10:30 Eastern = 13:30-14:30 UTC = 15:30-16:30 Spain
console.log('First hour (15:30 Spain):', determineTradingSession('2025-10-12T15:30:00')); // Should be first_hour
console.log('First hour (16:29 Spain):', determineTradingSession('2025-10-12T16:29:00')); // Should be first_hour
console.log('First hour (16:30 Spain):', determineTradingSession('2025-10-12T16:30:00')); // Should be midday

// Midday: 10:30-15:00 Eastern = 14:30-19:00 UTC = 16:30-21:00 Spain
console.log('Midday (17:00 Spain):', determineTradingSession('2025-10-12T17:00:00')); // Should be midday

// Power hour: 15:00-16:00 Eastern = 19:00-20:00 UTC = 21:00-22:00 Spain
console.log('Power hour (21:30 Spain):', determineTradingSession('2025-10-12T21:30:00')); // Should be power_hour

// After hours: 16:00-20:00 Eastern = 20:00-24:00 UTC = 22:00-02:00 Spain (next day)
console.log('After hours (22:30 Spain):', determineTradingSession('2025-10-12T22:30:00')); // Should be afterhours

// Test edge cases
console.log('\n=== Edge Cases ===');
console.log('Exactly 09:30 Eastern (15:30 Spain):', determineTradingSession('2025-10-12T15:30:00'));
console.log('Exactly 10:30 Eastern (16:30 Spain):', determineTradingSession('2025-10-12T16:30:00'));
console.log('Exactly 15:00 Eastern (21:00 Spain):', determineTradingSession('2025-10-12T21:00:00'));
console.log('Exactly 16:00 Eastern (22:00 Spain):', determineTradingSession('2025-10-12T22:00:00'));