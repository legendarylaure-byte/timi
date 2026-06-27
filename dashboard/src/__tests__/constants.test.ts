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
  it('has name and description for each category', () => {
    CONTENT_CATEGORIES.forEach((cat) => {
      expect(cat).toHaveProperty('name');
      expect(cat).toHaveProperty('description');
      expect(typeof cat.name).toBe('string');
      expect(cat.name.length).toBeGreaterThan(0);
    });
  });

  it('includes AI Explained and Deep Tech', () => {
    const names = CONTENT_CATEGORIES.map((c) => c.name);
    expect(names).toContain('AI Explained');
    expect(names).toContain('Deep Tech');
  });
});
