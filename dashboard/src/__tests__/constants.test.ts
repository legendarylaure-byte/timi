import { AGENT_ROLES, CONTENT_CATEGORIES } from '@/lib/constants';

describe('AGENT_ROLES', () => {
  it('has required fields for every agent', () => {
    AGENT_ROLES.forEach((role) => {
      expect(role).toHaveProperty('id');
      expect(role).toHaveProperty('name');
      expect(role).toHaveProperty('emoji');
      expect(role).toHaveProperty('color');
      expect(role).toHaveProperty('description');
      expect(typeof role.name).toBe('string');
      expect(typeof role.description).toBe('string');
      expect(role.name.length).toBeGreaterThan(0);
    });
  });

  it('includes key agent roles', () => {
    const ids = AGENT_ROLES.map((r) => r.id);
    expect(ids).toContain('scriptwriter');
    expect(ids).toContain('storyboard');
    expect(ids).toContain('publisher');
  });
});

describe('CONTENT_CATEGORIES', () => {
  it('has required fields for each category', () => {
    CONTENT_CATEGORIES.forEach((cat) => {
      expect(cat).toHaveProperty('name');
      expect(cat).toHaveProperty('description');
      expect(cat).toHaveProperty('group');
      expect(cat).toHaveProperty('isNews');
      expect(['pillar', 'news']).toContain(cat.group);
      expect(typeof cat.name).toBe('string');
      expect(cat.name.length).toBeGreaterThan(0);
    });
  });

  it('matches the backend canonical categories', () => {
    const names = CONTENT_CATEGORIES.map((c) => c.name);
    expect(names).toEqual([
      'AI News',
      'Science & Technology',
      'Programming & Software',
      'World News (24hr)',
      'Nepal News',
    ]);
  });

  it('flags news categories correctly', () => {
    const news = CONTENT_CATEGORIES.filter((c) => c.isNews);
    expect(news.map((c) => c.name)).toEqual(['World News (24hr)', 'Nepal News']);
  });
});
