import '@testing-library/jest-dom';
import { render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import App from './App';

const theme = createTheme();

const renderWithTheme = (component) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

jest.mock('./utils/api', () => {
  class MockApiError extends Error {
    constructor(message, status, originalError) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
      this.originalError = originalError;
    }
  }
  return {
    api: {
      health: jest.fn(),
      getClusters: jest.fn().mockResolvedValue([]),
      generateClusters: jest.fn(),
      createAction: jest.fn(),
      getActions: jest.fn().mockResolvedValue([]),
      completeAction: jest.fn(),
      refreshData: jest.fn(),
      getConsent: jest.fn(),
      updateConsent: jest.fn(),
      getDisclaimer: jest.fn(),
      runRetention: jest.fn(),
      getRetentionLog: jest.fn(),
    },
    formatPainPoint: (point) => point,
    getPainPointColor: () => '#000',
    ApiError: MockApiError,
  };
});

jest.mock('./hooks/useVoice', () => ({
  useVoiceGuidance: () => ({
    announce: jest.fn(),
    toggleGuidance: jest.fn(),
    guidanceEnabled: true,
    isSpeaking: false,
    isSupported: true,
    stop: jest.fn(),
  }),
}));

describe('App', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the app title', () => {
    renderWithTheme(<App />);
    expect(screen.getByText('SeniorCare Pulse')).toBeInTheDocument();
  });

  it('shows find groups button', () => {
    renderWithTheme(<App />);
    expect(screen.getByRole('button', { name: /find support groups/i })).toBeInTheDocument();
  });

  it('shows refresh button', () => {
    renderWithTheme(<App />);
    expect(screen.getByRole('button', { name: /refresh data/i })).toBeInTheDocument();
  });

  it('shows voice guidance toggle', () => {
    renderWithTheme(<App />);
    expect(screen.getByRole('button', { name: /turn off voice guidance/i })).toBeInTheDocument();
  });

  it('shows offline indicator when network error occurs', async () => {
    const { api, ApiError } = require('./utils/api');
    api.getClusters.mockRejectedValueOnce(
      new ApiError('Connection timeout', 0, new Error('Network error'))
    );

    renderWithTheme(<App />);
    
    await waitFor(() => {
      expect(screen.getByText('Offline')).toBeInTheDocument();
    });
  });
});

describe('ApiError', () => {
  it('creates error with status and message', () => {
    const { ApiError } = require('./utils/api');
    const error = new ApiError('Test error', 500, new Error('Original'));
    
    expect(error.message).toBe('Test error');
    expect(error.status).toBe(500);
    expect(error.originalError).toBeDefined();
    expect(error.name).toBe('ApiError');
  });
});