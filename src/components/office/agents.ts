export type AgentColor = "blue" | "orange" | "purple" | "green" | "yellow";
export type Accessory = "headset" | "key" | "marker" | "papers" | "cap";

export type Agent = {
  id: string;
  name: string;
  color: AgentColor;
  role: string;
  activity: string;
  /** Floor position (px) and base height the agent stands on. */
  x: number;
  y: number;
  z: number;
  seated?: boolean;
  accessory: Accessory;
  delay: number;
};

export const AGENTS: Agent[] = [
  { id: "atlas", name: "Atlas", color: "blue", role: "Builder", activity: "Coding SAMS-201", x: 190, y: 200, z: 30, seated: true, accessory: "headset", delay: 0 },
  { id: "ember", name: "Ember", color: "orange", role: "Keeper", activity: "Rotating API secrets", x: 515, y: 500, z: 0, accessory: "key", delay: 0.4 },
  { id: "iris", name: "Iris", color: "purple", role: "Planner", activity: "Mapping sprint board", x: 500, y: 120, z: 0, accessory: "marker", delay: 0.8 },
  { id: "moss", name: "Moss", color: "green", role: "Courier", activity: "Delivering PR docs", x: 360, y: 370, z: 0, accessory: "papers", delay: 1.2 },
  { id: "sunny", name: "Sunny", color: "yellow", role: "Guard", activity: "Verifying access", x: 270, y: 610, z: 0, accessory: "cap", delay: 1.6 },
];

export const agentClass = (c: AgentColor) => `agent-${c}`;
