export type Collection = {
  id: string;
  name: string;
  tags: string[];
  metadata: Record<string, string>;
  parentId?: string | null;
  fileCount: number;
  createdAt: string;
  updatedAt: string;
};
