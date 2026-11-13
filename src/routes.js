import React from "react";

import Admin from "./pages/admin.js";
import Landing from "./pages/landing.js";
import Login from "./pages/login.js";
import SignUp from "./pages/signup.js";
import { ForgotAccount, ResetPassword, VerifyEmail } from "./pages/recovery.js";
import CreateKingdom from "./pages/createkingdom.js";
import StatusContent from "./pages/home/status.js";
import NewsContent from "./pages/home/news.js";
import Galaxy from "./pages/galaxy.js";
import Message from "./pages/message.js";
import Scores from "./pages/home/scores.js";
import History from "./pages/home/history.js";
import Build from "./pages/build/build.js";
import Settle from "./pages/build/settle.js";
import Structures from "./pages/build/structures.js";
import MilitaryContent from "./pages/build/military.js";
import ProjectsContent from "./pages/build/projects.js";
import Missiles from "./pages/build/missiles.js";
import ConquerContent from "./pages/conquer/conquer.js";
import Attack from "./pages/conquer/attack.js";
import Spy from "./pages/conquer/spy.js";
import ShareIntel from "./pages/conquer/shareintel.js";
import LaunchMissiles from "./pages/conquer/launchmissiles.js";
import Schedule from "./pages/conquer/schedule.js";
import Primitives from "./pages/conquer/primitives.js";
import GalaxyPolitics from "./pages/politics/galaxypolitics.js";
import EmpirePolitics from "./pages/politics/empirepolitics.js";
import UniversePolitics from "./pages/politics/universepolitics.js";
import Help from "./pages/help/help.js";

/*
 * Every page of the app, in one place. Both the router (App.js) and the side navigation (components/navbar.js) read
 * this, so adding a page is one entry here.
 *
 * What a page receives is decided by where it sits:
 *   - game pages (`sections` below) need a signed-in player with a kingdom, and get {data, loading, updateData}
 *   - `publicRoutes` can be opened by anyone and get {logged, session} (and nothing else)
 * A page that needs something extra says so with `props`, a function of the app context.
 *
 * `notifs` lists the notification counters (data.notifs) that show as "(n)" next to a link.
 */

export const sections = [
  {
    title: "Home",
    path: "/status",
    notifs: ["news_kingdom", "news_galaxy", "messages"],
    pages: [
      { path: "/status", label: "Status", component: StatusContent },
      { path: "/news", label: "News", component: NewsContent, notifs: ["news_kingdom", "news_galaxy"] },
      {
        path: "/galaxy", label: "Galaxy", component: Galaxy,
        props: ({ data }) => ({ initialGalaxyId: data.galaxies_inverted[data.kingdomid.kd_id] }),
      },
      { path: "/message", label: "Message", component: Message, notifs: ["messages"] },
      { path: "/history", label: "History", component: History },
      { path: "/scores", label: "Scores", component: Scores },
    ],
  },
  {
    title: "Build",
    path: "/build",
    pages: [
      { path: "/build", label: "Overview", component: Build },
      { path: "/settle", label: "Settle", component: Settle },
      { path: "/structures", label: "Structures", component: Structures },
      { path: "/military", label: "Military", component: MilitaryContent },
      { path: "/projects", label: "Projects", component: ProjectsContent },
      { path: "/missiles", label: "Build Missiles", component: Missiles },
    ],
  },
  {
    title: "Conquer",
    path: "/conquer",
    notifs: ["shared"],
    pages: [
      { path: "/conquer", label: "Overview", component: ConquerContent },
      { path: "/attack", label: "Attack", component: Attack },
      { path: "/spy", label: "Spy", component: Spy },
      { path: "/shareintel", label: "Share Intel", component: ShareIntel },
      { path: "/launchmissiles", label: "Launch Missiles", component: LaunchMissiles },
      { path: "/schedule", label: "Schedule", component: Schedule },
      { path: "/primitives", label: "Primitives", component: Primitives },
    ],
  },
  {
    title: "Politics",
    path: "/galaxypolitics",
    pages: [
      { path: "/galaxypolitics", label: "Galaxy Politics", component: GalaxyPolitics },
      { path: "/empirepolitics", label: "Empire Politics", component: EmpirePolitics },
      { path: "/universepolitics", label: "Universe Politics", component: UniversePolitics },
    ],
  },
];

export const publicRoutes = [
  { path: "/", component: Landing, props: ({ logged }) => ({ logged }) },
  { path: "/login", component: Login, props: ({ logged }) => ({ logged }) },
  { path: "/signup", component: SignUp, props: ({ logged }) => ({ logged }) },
  { path: "/forgot", component: ForgotAccount },
  { path: "/resetpassword", component: ResetPassword },
  { path: "/verifyemail", component: VerifyEmail },
  { path: "/help", component: Help },
  { path: "/admin", component: Admin },
];

// Needs a signed-in player, but not a kingdom yet: this is where a new player makes theirs.
export const createKingdomRoute = {
  path: "/createkingdom",
  component: CreateKingdom,
  props: ({ loading, updateData, data }) => ({ loading, updateData, kingdomid: data.kingdomid, state: data.state }),
};

// The paths of one section's pages.
export const sectionPaths = (section) => section.pages.map((page) => page.path);

export const gamePages = sections.flatMap((section) => section.pages);

/** The props a game page gets: the shared ones, plus whatever the page asked for. */
export const propsFor = (route, context) => ({
  data: context.data,
  loading: context.loading,
  updateData: context.updateData,
  ...(route.props ? route.props(context) : {}),
});
