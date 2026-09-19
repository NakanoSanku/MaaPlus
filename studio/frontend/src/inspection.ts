import type { Project } from './types';

// An unrelated invalid locator must not prevent this recognition from being tested.
export function projectForLocator(project: Project, locatorId: string): Project {
  const mapping = new Map(project.locators.map(item => [item.id, item]));
  const needed = new Set<string>(), pending = [locatorId];
  while (pending.length) {
    const id = pending.pop()!;
    if (needed.has(id)) continue;
    needed.add(id);
    pending.push(...(mapping.get(id)?.children || []));
  }
  const locators = project.locators.filter(item => needed.has(item.id));
  const groups = new Set(locators.map(item => item.group_id));
  return { ...project, groups: project.groups.filter(group => groups.has(group.id)), locators };
}
