export interface Plan {
  working_directory: string
  build: BuildPlan[]
}

export interface BuildPlan {
  type: 'charm' | 'rock' | 'docker-image'
  name: string
  source_file: string
  source_directory: string
  output_type: 'file' | 'registry'
  output: string
}
