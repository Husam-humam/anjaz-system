export interface ApiResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  error: boolean;
  message: string;
  code: string;
  details: Record<string, string[]>;
}
