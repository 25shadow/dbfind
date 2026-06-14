export type Collection = {
  id: string;
  name: string;
  sourceRegion?: string | null;
  sourceYear?: number | null;
  sourceType?: string | null;
  sourceScope?: string | null;
  parentId?: string | null;
  fileCount: number;
  createdAt: string;
  updatedAt: string;
};
