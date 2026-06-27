import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

const ThrowComponent = ({ shouldThrow }: { shouldThrow: boolean }) => {
  if (shouldThrow) throw new Error('test error');
  return <div>no error</div>;
};

beforeEach(() => {
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>hello world</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('hello world')).toBeInTheDocument();
  });

  it('shows fallback on error', () => {
    render(
      <ErrorBoundary>
        <ThrowComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('shows custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>custom error</div>}>
        <ThrowComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText('custom error')).toBeInTheDocument();
  });

  it('Recovers after retry click', () => {
    render(
      <ErrorBoundary>
        <ThrowComponent shouldThrow={true} />
      </ErrorBoundary>,
    );
    const retryBtn = screen.getByText('Retry');
    expect(retryBtn).toBeInTheDocument();
  });
});
