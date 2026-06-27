export const ACCEPTED_DATA_FILE_EXTENSIONS = [".xlsx", ".xls", ".xlsm", ".xlsb", ".et", ".ods", ".csv"] as const;

export const ACCEPTED_DATA_FILE_TYPES = ACCEPTED_DATA_FILE_EXTENSIONS.join(",");
