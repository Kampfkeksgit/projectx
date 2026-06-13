/**
 * Database Helper Utilities
 * Provides utility functions for database operations, query building, and error handling
 */

/**
 * Build an UPDATE query dynamically based on fields and where clause
 * @param {string} table - Table name
 * @param {Object} fields - Object with field names as keys and values to update
 * @param {string} whereClause - WHERE clause (e.g., 'id = ?')
 * @param {Array} whereValues - Values for WHERE clause placeholders
 * @returns {Object} { query, values } - Query string and parameters
 */
export function buildUpdateQuery(table, fields, whereClause, whereValues = []) {
  if (!table || !fields || Object.keys(fields).length === 0) {
    throw new Error('Invalid parameters for buildUpdateQuery');
  }

  const updateFields = [];
  const updateValues = [];

  // Build SET clause
  for (const [key, value] of Object.entries(fields)) {
    // Sanitize field names to prevent SQL injection
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key)) {
      throw new Error(`Invalid field name: ${key}`);
    }
    updateFields.push(`${key} = ?`);
    updateValues.push(value);
  }

  // Add updated_at timestamp
  updateFields.push('updated_at = CURRENT_TIMESTAMP');

  // Combine with WHERE values
  const allValues = [...updateValues, ...whereValues];

  const query = `UPDATE ${table} SET ${updateFields.join(', ')} WHERE ${whereClause}`;

  return { query, values: allValues };
}

/**
 * Build an INSERT query dynamically
 * @param {string} table - Table name
 * @param {Object} data - Object with field names as keys and values to insert
 * @returns {Object} { query, values } - Query string and parameters
 */
export function buildInsertQuery(table, data) {
  if (!table || !data || Object.keys(data).length === 0) {
    throw new Error('Invalid parameters for buildInsertQuery');
  }

  const fields = Object.keys(data);
  const values = Object.values(data);

  // Validate field names
  fields.forEach((field) => {
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(field)) {
      throw new Error(`Invalid field name: ${field}`);
    }
  });

  const placeholders = fields.map(() => '?').join(', ');
  const query = `INSERT INTO ${table} (${fields.join(', ')}) VALUES (${placeholders})`;

  return { query, values };
}

/**
 * Build a SELECT query with optional WHERE and ORDER BY
 * @param {string} table - Table name
 * @param {Array} columns - Array of column names (default: ['*'])
 * @param {string} whereClause - WHERE clause (optional)
 * @param {Array} whereValues - Values for WHERE clause (optional)
 * @param {Object} options - { orderBy, limit, offset }
 * @returns {Object} { query, values } - Query string and parameters
 */
export function buildSelectQuery(table, columns = ['*'], whereClause = null, whereValues = [], options = {}) {
  if (!table) {
    throw new Error('Table name is required');
  }

  const columnList = Array.isArray(columns) ? columns.join(', ') : columns;
  let query = `SELECT ${columnList} FROM ${table}`;

  if (whereClause) {
    query += ` WHERE ${whereClause}`;
  }

  if (options.orderBy) {
    query += ` ORDER BY ${options.orderBy}`;
  }

  if (options.limit) {
    query += ` LIMIT ${parseInt(options.limit)}`;
  }

  if (options.offset) {
    query += ` OFFSET ${parseInt(options.offset)}`;
  }

  return { query, values: whereValues };
}

/**
 * Handle database errors with context
 * @param {Error} error - The error object
 * @param {string} context - Context description (what was being done)
 * @param {Object} details - Additional details (optional)
 * @returns {Object} { message, code, originalError, details }
 */
export function handleDbError(error, context = 'Database operation', details = {}) {
  const errorResponse = {
    message: 'Database error',
    code: 'DB_ERROR',
    originalError: error.message,
    context,
    details,
  };

  // Handle specific SQLite errors
  if (error.message.includes('UNIQUE constraint failed')) {
    errorResponse.code = 'UNIQUE_CONSTRAINT_VIOLATION';
    errorResponse.message = 'This record already exists';
  } else if (error.message.includes('FOREIGN KEY constraint failed')) {
    errorResponse.code = 'FOREIGN_KEY_CONSTRAINT_VIOLATION';
    errorResponse.message = 'Referenced record does not exist or cannot be deleted';
  } else if (error.message.includes('NOT NULL constraint failed')) {
    errorResponse.code = 'NOT_NULL_CONSTRAINT_VIOLATION';
    errorResponse.message = 'Required field is missing';
  } else if (error.message.includes('no such table')) {
    errorResponse.code = 'TABLE_NOT_FOUND';
    errorResponse.message = 'Table does not exist';
  }

  // Log error for debugging
  console.error(`[DB ERROR] ${context}:`, error);

  return errorResponse;
}

/**
 * Format a timestamp in ISO 8601 format
 * @param {Date|string|number} date - Date to format (default: current time)
 * @returns {string} ISO 8601 formatted timestamp
 */
export function formatTimestamp(date = new Date()) {
  let d;

  if (typeof date === 'string') {
    d = new Date(date);
  } else if (typeof date === 'number') {
    d = new Date(date);
  } else {
    d = date instanceof Date ? date : new Date();
  }

  if (isNaN(d.getTime())) {
    d = new Date();
  }

  return d.toISOString();
}

/**
 * Validate Guild ID format
 * @param {string} guildId - Guild ID to validate
 * @returns {boolean} Whether the ID is valid
 */
export function isValidGuildId(guildId) {
  return typeof guildId === 'string' && /^\d{15,21}$/.test(guildId);
}

/**
 * Validate Discord User ID format
 * @param {string} userId - User ID to validate
 * @returns {boolean} Whether the ID is valid
 */
export function isValidUserId(userId) {
  return typeof userId === 'string' && /^\d{15,21}$/.test(userId);
}

/**
 * Validate Channel ID format
 * @param {string} channelId - Channel ID to validate
 * @returns {boolean} Whether the ID is valid
 */
export function isValidChannelId(channelId) {
  return typeof channelId === 'string' && /^\d{15,21}$/.test(channelId);
}

/**
 * Parse JSON string safely
 * @param {jsonString} string - JSON string to parse
 * @param {*} fallback - Fallback value if parsing fails
 * @returns {*} Parsed object or fallback
 */
export function safeJsonParse(jsonString, fallback = null) {
  try {
    return JSON.parse(jsonString);
  } catch (e) {
    console.error('Failed to parse JSON:', e);
    return fallback;
  }
}

/**
 * Sanitize user input to prevent SQL injection
 * @param {string} input - User input to sanitize
 * @returns {string} Sanitized input
 */
export function sanitizeInput(input) {
  if (typeof input !== 'string') {
    return input;
  }

  // Basic sanitization - remove potentially harmful characters
  return input.replace(/['"]/g, '').trim();
}

/**
 * Create a simple query logger
 * @param {string} query - SQL query
 * @param {Array} values - Query parameters
 * @param {number} executionTime - Execution time in ms
 */
export function logQuery(query, values = [], executionTime = 0) {
  const redactedValues = values.map((v) => {
    if (typeof v === 'string' && v.length > 50) {
      return v.substring(0, 47) + '...';
    }
    return v;
  });

  console.log(`[Query] ${query}`);
  console.log(`[Params] ${JSON.stringify(redactedValues)}`);
  if (executionTime > 0) {
    console.log(`[Time] ${executionTime}ms`);
  }
}

export default {
  buildUpdateQuery,
  buildInsertQuery,
  buildSelectQuery,
  handleDbError,
  formatTimestamp,
  isValidGuildId,
  isValidUserId,
  isValidChannelId,
  safeJsonParse,
  sanitizeInput,
  logQuery,
};
