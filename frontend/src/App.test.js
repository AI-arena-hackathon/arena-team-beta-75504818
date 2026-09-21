import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
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

jest.mock('./utils/api', () => ({
  api: {
    health: jest.fn(),
    getClusters: jest.fn(),
    generateClusters: jest.fn(),
    createAction: jest.fn(),
    getActions: jest.fn(),
    completeAction: jest.fn(),
    refreshData: jest.fn(),
  },
  formatPainPoint: (point) => point,
  getPainPointColor: () => '#000',
}));

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
});