/**
 * Circuit.AI JavaScript SDK Errors
 * 
 * Custom error classes for the Circuit.AI API.
 */

export class CircuitAIError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CircuitAIError';
  }
}

export class AuthenticationError extends CircuitAIError {
  constructor(message: string = 'Authentication failed') {
    super(message);
    this.name = 'AuthenticationError';
  }
}

export class RateLimitError extends CircuitAIError {
  public retryAfter?: number;

  constructor(message: string = 'Rate limit exceeded', retryAfter?: number) {
    super(message);
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}

export class APIError extends CircuitAIError {
  public statusCode?: number;
  public errorCode?: string;

  constructor(message: string, statusCode?: number, errorCode?: string) {
    super(message);
    this.name = 'APIError';
    this.statusCode = statusCode;
    this.errorCode = errorCode;
  }
}
